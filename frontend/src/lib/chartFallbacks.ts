const WORKFLOWS = ['Portfolio', 'Trade', '10-K', 'Client', 'Risk', 'KYC']

function sv(seed: number) {
  const x = Math.sin(seed * 9301 + 49297) * 233280
  return x - Math.floor(x)
}

function sr(seed: number, lo: number, hi: number) {
  return lo + sv(seed) * (hi - lo)
}

export function fallbackLatencyBreakdown() {
  return WORKFLOWS.map((agent, i) => ({
    agent,
    prompt: Math.round(sr(i + 1, 90, 240)),
    tool_call: Math.round(sr(i + 7, 320, 1180)),
    synthesis: Math.round(sr(i + 13, 120, 420)),
    output: Math.round(sr(i + 17, 60, 220)),
  }))
}

export function fallbackLatencyPercentiles(points = 30) {
  return Array.from({ length: points }, (_, i) => ({
    time: `${i}`,
    p50: Math.round(sr(i + 1, 380, 760)),
    p95: Math.round(sr(i + 5, 1200, 2100)),
    p99: Math.round(sr(i + 9, 1900, 3200)),
  }))
}

export function fallbackTokenCost(points = 30) {
  return Array.from({ length: points }, (_, i) => ({
    time: `${i}`,
    tokens: Math.round(sr(i + 1, 3800, 11200)),
    cost: parseFloat(sr(i + 7, 0.16, 0.72).toFixed(3)),
  }))
}

export function fallbackErrorRecovery() {
  return WORKFLOWS.map((agent, i) => ({
    agent,
    recovery_rate: Math.round(sr(i + 1, 74, 97)),
    total_retries: Math.round(sr(i + 5, 2, 14)),
    session_crashes: Math.round(sr(i + 11, 0, 4)),
  }))
}

export function fallbackTSRByAgent() {
  return WORKFLOWS.map((agent, i) => ({
    agent,
    tsr: Math.round(sr(i + 1, 78, 99)),
  }))
}

export function fallbackDecisionTurns() {
  return WORKFLOWS.map((agent, i) => {
    const avg_turns = Math.round(sr(i + 1, 4, 15))
    return {
      agent,
      avg_turns,
      loops_detected: avg_turns > 12 ? Math.round(sr(i + 7, 1, 4)) : 0,
    }
  })
}

export function fallbackToolAccuracy() {
  return [
    'Bloomberg API',
    'Internal GL',
    'Risk Engine',
    'Custodian API',
    'RAG Doc Store',
    'Compliance DB',
    'Client CRM',
  ].map((tool, i) => ({
    tool,
    accuracy: Math.round(sr(i + 1, 79, 97)),
  }))
}

export function fallbackHallucinationRates() {
  return WORKFLOWS.map((agent, i) => ({
    agent,
    hallucination_rate: parseFloat(sr(i + 1, agent === '10-K' ? 3.4 : 0.8, agent === '10-K' ? 6.8 : 3.1).toFixed(2)),
  }))
}

export function fallbackHallucinationTrend(points = 30) {
  return Array.from({ length: points }, (_, i) => ({
    time: `${i}`,
    rate: parseFloat(sr(i + 1, 0.7, 4.8).toFixed(2)),
  }))
}

export function fallbackScoresTrend(points = 30) {
  return Array.from({ length: points }, (_, i) => ({
    time: `${i}`,
    accuracy: parseFloat(sr(i + 1, 0.74, 0.96).toFixed(2)),
    helpfulness: parseFloat(sr(i + 7, 0.72, 0.95).toFixed(2)),
    relevance: parseFloat(sr(i + 11, 0.7, 0.94).toFixed(2)),
  }))
}

export function fallbackAgentsSummary() {
  return [
    { name: 'portfolio_rebalancer', framework: 'langgraph', total_runs: 76, tsr: 95, avg_latency_ms: 621, p95_latency_ms: 1330, avg_cost_per_task: 0.0342 },
    { name: 'trade_reconcile', framework: 'langchain', total_runs: 63, tsr: 98, avg_latency_ms: 544, p95_latency_ms: 1182, avg_cost_per_task: 0.0278 },
    { name: 'tenk_analyst', framework: 'openai-agents', total_runs: 34, tsr: 81, avg_latency_ms: 1493, p95_latency_ms: 2621, avg_cost_per_task: 0.0526 },
    { name: 'client_reporter', framework: 'pydantic-ai', total_runs: 52, tsr: 96, avg_latency_ms: 701, p95_latency_ms: 1452, avg_cost_per_task: 0.0395 },
  ]
}
