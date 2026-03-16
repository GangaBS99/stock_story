// All API calls go through the Vite proxy: /api → http://localhost:8500

const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

// ── Types ────────────────────────────────────────────────────

export interface KPIs {
  tsr: number
  tool_accuracy: number
  hallucination_rate: number
  hitl_count: number
  p95_latency_ms: number
  avg_latency_ms: number
  avg_cost_per_task: number
  total_runs: number
  completed_runs: number
  failed_runs: number
}

export interface LatencyPoint {
  time: string
  p50: number
  p95: number
  p99: number
}

export interface LatencyBreakdown {
  agent: string
  prompt: number
  tool_call: number
  synthesis: number
  output: number
  total: number
}

export interface TokenCostPoint {
  time: string
  tokens: number
  cost: number
}

export interface ErrorRecovery {
  agent: string
  recovery_rate: number
  total_retries: number
  session_crashes: number
}

export interface ToolAccuracy {
  tool: string
  accuracy: number
}

export interface TSRByAgent {
  agent: string
  tsr: number
  total: number
}

export interface ScoresTrendPoint {
  time: string
  [key: string]: number | string
}

export interface HallucinationRate {
  agent: string
  hallucination_rate: number
}

export interface HallucinationTrendPoint {
  time: string
  rate: number
}

export interface DecisionTurns {
  agent: string
  avg_turns: number
  loops_detected: number
  total_runs: number
}

export interface AgentSummary {
  name: string
  description: string
  framework: string
  version: string
  total_runs: number
  completed_runs: number
  failed_runs: number
  tsr: number
  avg_latency_ms: number
  p95_latency_ms: number
}

// ── Fetchers ─────────────────────────────────────────────────

export const api = {
  kpis: () => get<KPIs>('/dashboard/kpis'),
  latencyPercentiles: (points = 30) => get<LatencyPoint[]>(`/dashboard/latency-percentiles?points=${points}`),
  latencyBreakdown: () => get<LatencyBreakdown[]>('/dashboard/latency-breakdown'),
  tokenCost: (points = 30) => get<TokenCostPoint[]>(`/dashboard/token-cost?points=${points}`),
  errorRecovery: () => get<ErrorRecovery[]>('/dashboard/error-recovery'),
  toolAccuracy: () => get<ToolAccuracy[]>('/dashboard/tool-accuracy'),
  tsrByAgent: () => get<TSRByAgent[]>('/dashboard/tsr-by-agent'),
  scoresTrend: (points = 30) => get<ScoresTrendPoint[]>(`/dashboard/scores-trend?points=${points}`),
  hallucinationRate: () => get<HallucinationRate[]>('/dashboard/hallucination-rate'),
  hallucinationTrend: (points = 30) => get<HallucinationTrendPoint[]>(`/dashboard/hallucination-trend?points=${points}`),
  decisionTurns: () => get<DecisionTurns[]>('/dashboard/decision-turns'),
  agentsSummary: () => get<AgentSummary[]>('/dashboard/agents-summary'),
}
