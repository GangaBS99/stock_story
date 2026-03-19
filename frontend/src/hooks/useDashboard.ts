import { useQuery } from '@tanstack/react-query'
import { api } from '../api/controlPlane'

// Global polling interval — set to 0 when paused
const POLL_MS = 10_000

function usePolling(paused: boolean) {
  return paused ? false : POLL_MS
}

export function useKPIs(paused = false) {
  return useQuery({
    queryKey: ['kpis'],
    queryFn: api.kpis,
    refetchInterval: usePolling(paused),
  })
}

export function useLatencyPercentiles(paused = false) {
  return useQuery({
    queryKey: ['latency-percentiles'],
    queryFn: () => api.latencyPercentiles(30),
    refetchInterval: usePolling(paused),
  })
}

export function useLatencyBreakdown(paused = false) {
  return useQuery({
    queryKey: ['latency-breakdown'],
    queryFn: api.latencyBreakdown,
    refetchInterval: usePolling(paused),
  })
}

export function useTokenCost(paused = false) {
  return useQuery({
    queryKey: ['token-cost'],
    queryFn: () => api.tokenCost(30),
    refetchInterval: usePolling(paused),
  })
}

export function useErrorRecovery(paused = false) {
  return useQuery({
    queryKey: ['error-recovery'],
    queryFn: api.errorRecovery,
    refetchInterval: usePolling(paused),
  })
}

export function useToolAccuracy(paused = false) {
  return useQuery({
    queryKey: ['tool-accuracy'],
    queryFn: api.toolAccuracy,
    refetchInterval: usePolling(paused),
  })
}

export function useTSRByAgent(paused = false) {
  return useQuery({
    queryKey: ['tsr-by-agent'],
    queryFn: api.tsrByAgent,
    refetchInterval: usePolling(paused),
  })
}

export function useScoresTrend(paused = false) {
  return useQuery({
    queryKey: ['scores-trend'],
    queryFn: () => api.scoresTrend(30),
    refetchInterval: usePolling(paused),
  })
}

export function useHallucinationRate(paused = false) {
  return useQuery({
    queryKey: ['hallucination-rate'],
    queryFn: api.hallucinationRate,
    refetchInterval: usePolling(paused),
  })
}

export function useHallucinationTrend(paused = false) {
  return useQuery({
    queryKey: ['hallucination-trend'],
    queryFn: () => api.hallucinationTrend(30),
    refetchInterval: usePolling(paused),
  })
}

export function useDecisionTurns(paused = false) {
  return useQuery({
    queryKey: ['decision-turns'],
    queryFn: api.decisionTurns,
    refetchInterval: usePolling(paused),
  })
}

export function useAgentsSummary(paused = false) {
  return useQuery({
    queryKey: ['agents-summary'],
    queryFn: api.agentsSummary,
    refetchInterval: usePolling(paused),
  })
}

export function useAgentTraces(agentName: string | null, paused = false) {
  return useQuery({
    queryKey: ['agent-traces', agentName],
    queryFn: () => api.agentTraces(agentName as string, 30),
    enabled: Boolean(agentName),
    refetchInterval: usePolling(paused),
  })
}

export function useAgentTraceDetail(traceId: string | null, paused = false) {
  return useQuery({
    queryKey: ['agent-trace-detail', traceId],
    queryFn: () => api.agentTraceDetail(traceId as string),
    enabled: Boolean(traceId),
    refetchInterval: usePolling(paused),
  })
}
