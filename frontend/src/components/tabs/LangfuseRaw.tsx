import { useState, useMemo } from 'react'
import { getLangfuseAgentUrl } from '../../api/controlPlane'

const viteEnv =
  ((import.meta as unknown as { env?: Record<string, string | undefined> }).env) || {}
const PROXY_URL = (viteEnv.VITE_LANGFUSE_PROXY_URL || 'http://localhost:3001').replace(/\/$/, '')

interface Props {
  paused: boolean
}

export default function LangfuseRaw({ paused: _paused }: Props) {
  const directUrl = useMemo(() => getLangfuseAgentUrl(), [])
  const [iframeError, setIframeError] = useState(false)

  if (iframeError) {
    return (
      <div className="card flex flex-col items-center justify-center gap-5 py-16">
        <div className="text-lg font-semibold text-white">Langfuse</div>
        <div className="text-xs text-sub text-center max-w-md">
          Embedded view unavailable. Start the iframe proxy then reload:
        </div>
        <code className="text-xs text-cyan bg-black/40 px-3 py-1.5 rounded">
          node langfuse-proxy.mjs
        </code>
        <div className="flex gap-3 mt-2">
          <button
            onClick={() => setIframeError(false)}
            className="px-4 py-2 rounded border border-border text-sub text-xs hover:bg-white/5 transition-colors"
          >
            Retry embed
          </button>
          <a
            href={directUrl}
            target="_blank"
            rel="noreferrer"
            className="px-4 py-2 rounded border border-cyan text-cyan text-xs font-semibold hover:bg-white/5 transition-colors"
          >
            Open in new tab
          </a>
        </div>
      </div>
    )
  }

  return (
    <div className="w-full -mx-6 -my-5" style={{ height: 'calc(100vh - 110px)' }}>
      <iframe
        src={PROXY_URL}
        title="Langfuse"
        className="w-full h-full border-0"
        onError={() => setIframeError(true)}
      />
    </div>
  )
}
