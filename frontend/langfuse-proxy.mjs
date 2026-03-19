import http from 'node:http'
import { URL } from 'node:url'

const LANGFUSE_URL = (process.env.LANGFUSE_URL || process.env.VITE_LANGFUSE_URL || 'http://localhost:3000').replace(/\/$/, '')
const PROXY_PORT = Number(process.env.LANGFUSE_PROXY_PORT || 3001)

const target = new URL(LANGFUSE_URL)
const isHttps = target.protocol === 'https:'
const transport = isHttps ? (await import('node:https')).default : http
const targetPort = Number(target.port) || (isHttps ? 443 : 80)

const STRIP_HEADERS = ['x-frame-options', 'content-security-policy']

const server = http.createServer((clientReq, clientRes) => {
  const proxyReq = transport.request(
    {
      hostname: target.hostname,
      port: targetPort,
      path: clientReq.url,
      method: clientReq.method,
      headers: { ...clientReq.headers, host: target.host },
    },
    (proxyRes) => {
      const headers = { ...proxyRes.headers }
      for (const h of STRIP_HEADERS) delete headers[h]
      clientRes.writeHead(proxyRes.statusCode, headers)
      proxyRes.pipe(clientRes)
    },
  )
  proxyReq.on('error', (err) => {
    clientRes.writeHead(502)
    clientRes.end('Langfuse unreachable: ' + err.message)
  })
  clientReq.pipe(proxyReq)
})

server.on('upgrade', (clientReq, clientSocket, _head) => {
  const proxyReq = transport.request({
    hostname: target.hostname,
    port: targetPort,
    path: clientReq.url,
    method: 'GET',
    headers: { ...clientReq.headers, host: target.host },
  })
  proxyReq.on('upgrade', (_proxyRes, proxySocket, proxyHead) => {
    const resHeaders = Object.entries(_proxyRes.headers)
      .map(([k, v]) => `${k}: ${v}`)
      .join('\r\n')
    clientSocket.write(`HTTP/1.1 101 Switching Protocols\r\n${resHeaders}\r\n\r\n`)
    if (proxyHead.length) proxySocket.write(proxyHead)
    proxySocket.pipe(clientSocket)
    clientSocket.pipe(proxySocket)
  })
  proxyReq.on('error', () => clientSocket.destroy())
  proxyReq.end()
})

server.listen(PROXY_PORT, () => {
  console.log(`Langfuse iframe proxy  http://localhost:${PROXY_PORT}  →  ${LANGFUSE_URL}`)
})
