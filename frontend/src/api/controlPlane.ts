// All API calls go through the Vite proxy: /api → http://localhost:8500

const BASE = '/api'

const viteEnv =
  ((import.meta as unknown as { env?: Record<string, string | undefined> }).env) || {}
const LANGFUSE_BASE_URL = (viteEnv.VITE_LANGFUSE_URL || 'http://localhost:3000').replace(/\/$/, '')

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
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
  avg_cost_per_task: number
}

export interface AgentTrace {
  trace_id: string
  agent_name: string
  run_id: string
  status: string
  timestamp: string
  latency_ms: number
  cost: number
  turns: number
  session_id: string
  user_id: string
  input_preview: string
  output_preview: string
}

export interface AgentTraceDetail {
  source: 'langfuse' | 'run_tracker' | 'none'
  trace_id: string
  run_id?: string
  timestamp?: string
  latency_ms?: number
  cost?: number
  turns?: number
  status?: string
  session_id?: string
  user_id?: string
  name?: string
  input?: unknown
  output?: unknown
  metadata?: unknown
  scores?: unknown[]
  observations?: Array<{
    id: string
    parent_id: string
    type: string
    name: string
    level: string
    start_time: string
    end_time: string
    input_preview: string
    output_preview: string
    metadata: unknown
  }>
  raw_trace?: unknown
  error?: string
}

export interface PromptSummary {
  name: string
  latest_version: number
  latest_environment: string
  latest_preview: string
  labels: string[]
  active_by_env: Record<string, number>
  version_count: number
  updated_at: string
}

export interface PromptVersion {
  name: string
  version: number
  environment: string
  prompt: string
  labels: string[]
  config: Record<string, unknown>
  created_by: string
  created_at: string
  updated_at: string
  is_active: boolean
}

export interface PromptImportResult {
  status: string
  imported: number
  scanned_files: number
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
  agentTraces: (agentName: string, limit = 30) =>
    get<AgentTrace[]>(`/dashboard/agent-traces?agent_name=${encodeURIComponent(agentName)}&limit=${limit}`),
  agentTraceDetail: (traceId: string) =>
    get<AgentTraceDetail>(`/dashboard/agent-traces/${encodeURIComponent(traceId)}`),
  prompts: () => get<PromptSummary[]>('/prompts'),
  promptVersions: (name: string) => get<PromptVersion[]>(`/prompts/${encodeURIComponent(name)}/versions`),
  createPromptVersion: (payload: {
    name: string
    prompt: string
    environment: string
    labels: string[]
    config: Record<string, unknown>
    created_by: string
    activate: boolean
  }) => post<PromptVersion>('/prompts', payload),
  activatePromptVersion: (name: string, version: number, environment: string) =>
    post<{ name: string; version: number; environment: string; status: string }>(
      `/prompts/${encodeURIComponent(name)}/activate`,
      { version, environment }
    ),
  importPromptsFromSource: () => post<PromptImportResult>('/prompts/import-source', {}),
}

export function getLangfuseAgentUrl(agentName?: string): string {
  // Langfuse v3 is project-scoped; /traces may 404 on base install.
  // Use root so auth redirect works reliably inside iframe.
  const rootUrl = `${LANGFUSE_BASE_URL}/`
  if (!agentName) return rootUrl
  // Best-effort hint only; ignored by Langfuse if unsupported.
  return `${rootUrl}?search=${encodeURIComponent(agentName)}`
}
