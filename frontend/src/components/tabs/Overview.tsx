import { useState } from 'react'
import { useKPIs, useScoresTrend, useAgentsSummary, useAgentTraces, useAgentTraceDetail } from '../../hooks/useDashboard'
import MultiLineChart from '../charts/MultiLineChart'
import { fallbackScoresTrend } from '../../lib/chartFallbacks'
import { THEME } from '../../theme'

interface Props { paused: boolean }

const SCORE_COLORS = [THEME.cyan, THEME.green, THEME.amber, THEME.purple, THEME.blue, THEME.red]

function parseTrendKey(key: string): { scoreLabel: string; agentName: string } {
  const [agentName, scoreLabel] = key.includes('::') ? key.split('::', 2) : ['all', key]
  return { scoreLabel, agentName }
}

function pretty(value: unknown): string {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

interface ObservationNode {
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
}

function buildObservationRows(observations: ObservationNode[]): Array<{ node: ObservationNode; depth: number }> {
  const byParent: Record<string, ObservationNode[]> = {}
  for (const node of observations) {
    const key = node.parent_id || '__root__'
    byParent[key] = byParent[key] || []
    byParent[key].push(node)
  }

  const rows: Array<{ node: ObservationNode; depth: number }> = []
  const visit = (parentId: string, depth: number) => {
    const children = byParent[parentId] || []
    for (const child of children) {
      rows.push({ node: child, depth })
      visit(child.id, depth + 1)
    }
  }

  visit('__root__', 0)
  return rows
}

function StatCard({ label, value, sub, color = 'text-cyan' }: {
  label: string; value: string | number; sub?: string; color?: string
}) {
  return (
    <div className="card flex flex-col gap-1">
      <span className="text-[10px] font-mono text-gray-500 uppercase tracking-widest">{label}</span>
      <span className={`text-2xl font-mono font-semibold ${color}`}>{value}</span>
      {sub && <span className="text-xs text-gray-500">{sub}</span>}
    </div>
  )
}

export default function Overview({ paused }: Props) {
  const { data: kpis } = useKPIs(paused)
  const { data: rawTrend = [] } = useScoresTrend(paused)
  const { data: rawAgents = [] } = useAgentsSummary(paused)
  const trend = rawTrend.length > 0 ? rawTrend : fallbackScoresTrend()
  const agents = rawAgents
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null)
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null)
  const { data: agentTraces = [], isFetching: tracesLoading } = useAgentTraces(selectedAgent, paused)
  const { data: selectedTraceDetail, isFetching: traceDetailLoading } = useAgentTraceDetail(selectedTraceId, paused)

  // Collect unique score keys across all points (not only first point).
  // Some runs may emit different score names over time.
  const scoreKeys = Array.from(
    new Set(
      trend.flatMap((point) => Object.keys(point).filter((k) => k !== 'time'))
    )
  )

  // Many score series are sparse (emitted only on specific runs).
  // Carry forward the last known value so each eval renders as a continuous line.
  const lastSeen: Record<string, number | undefined> = {}
  const trendForChart: Record<string, unknown>[] = trend.map((point) => {
    const p = point as Record<string, unknown>
    const row: Record<string, unknown> = { time: String(p.time ?? '') }
    for (const key of scoreKeys) {
      const raw = p[key]
      if (typeof raw === 'number') {
        lastSeen[key] = raw
        row[key] = raw
      } else if (typeof lastSeen[key] === 'number') {
        row[key] = lastSeen[key]
      }
    }
    return row
  })
  const observationRows = buildObservationRows((selectedTraceDetail?.observations ?? []) as ObservationNode[])

  return (
    <div className="space-y-6">
      {/* KPI cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
        <StatCard
          label="Task Success Rate"
          value={kpis ? `${kpis.tsr}%` : '—'}
          sub={kpis ? `${kpis.completed_runs}/${kpis.total_runs} runs` : ''}
          color={
            typeof kpis?.tsr === 'number'
              ? kpis.tsr >= 90 ? 'text-green' : kpis.tsr >= 70 ? 'text-yellow' : 'text-red'
              : 'text-gray-400'
          }
        />
        <StatCard label="Tool Accuracy" value={kpis ? `${kpis.tool_accuracy}%` : '—'} color="text-cyan" />
        <StatCard
          label="Hallucination"
          value={kpis ? `${kpis.hallucination_rate}%` : '—'}
          color={
            typeof kpis?.hallucination_rate === 'number'
              ? kpis.hallucination_rate < 3 ? 'text-green' : kpis.hallucination_rate < 7 ? 'text-yellow' : 'text-red'
              : 'text-gray-400'
          }
        />
        <StatCard label="HITL Reviews" value={kpis?.hitl_count ?? '—'} color="text-purple" />
        <StatCard label="P95 Latency" value={kpis ? `${kpis.p95_latency_ms}ms` : '—'} color="text-yellow" />
        <StatCard label="Avg Latency" value={kpis ? `${kpis.avg_latency_ms}ms` : '—'} color="text-gray-300" />
        <StatCard label="$/Task" value={kpis ? `$${kpis.avg_cost_per_task}` : '—'} color="text-orange" />
      </div>

      {/* Scores trend */}
      <div className="card">
        <div className="card-title">Evaluation Score Trends</div>
        <MultiLineChart
          data={trendForChart}
          lines={scoreKeys.map((k, i) => ({
            key: k,
            color: SCORE_COLORS[i % SCORE_COLORS.length],
            label: (() => {
              const { scoreLabel, agentName } = parseTrendKey(k)
              return `${scoreLabel} (${agentName})`
            })(),
          }))}
          yDomain={[0, 1]}
          height={220}
        />
      </div>

      {/* Agents table */}
      <div className="card">
        <div className="card-title">Registered Agents</div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs font-mono">
            <thead>
              <tr className="border-b border-border text-gray-500">
                <th className="text-left py-2 pr-4">Agent</th>
                <th className="text-left py-2 pr-4">Framework</th>
                <th className="text-right py-2 pr-4">Runs</th>
                <th className="text-right py-2 pr-4">TSR</th>
                <th className="text-right py-2 pr-4">Avg Lat</th>
                <th className="text-right py-2 pr-4">P95 Lat</th>
                <th className="text-right py-2">$/Task</th>
              </tr>
            </thead>
            <tbody>
              {agents.map((a) => (
                <tr
                  key={a.name}
                  className={`border-b border-border/50 hover:bg-white/5 cursor-pointer ${
                    selectedAgent === a.name ? 'bg-white/10' : ''
                  }`}
                  onClick={() => {
                    setSelectedAgent(a.name)
                    setSelectedTraceId(null)
                  }}
                  title={`Show ${a.name} traces`}
                >
                  <td className="py-2 pr-4 text-white">{a.name}</td>
                  <td className="py-2 pr-4 text-gray-400">{a.framework}</td>
                  <td className="py-2 pr-4 text-right text-gray-300">{a.total_runs}</td>
                  <td className={`py-2 pr-4 text-right font-semibold ${
                    a.tsr >= 90 ? 'text-green' : a.tsr >= 70 ? 'text-yellow' : 'text-red'
                  }`}>{a.tsr}%</td>
                  <td className="py-2 pr-4 text-right text-gray-300">{a.avg_latency_ms}ms</td>
                  <td className="py-2 pr-4 text-right text-gray-300">{a.p95_latency_ms}ms</td>
                  <td className="py-2 text-right text-orange">${(a.avg_cost_per_task ?? 0).toFixed(4)}</td>
                </tr>
              ))}
              {agents.length === 0 && (
                <tr>
                  <td className="py-3 pr-4 text-sub" colSpan={7}>
                    No agents available yet. Trigger at least one instrumented run to populate agents.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {selectedAgent && (
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <div className="card-title mb-0">Agent Traces · {selectedAgent}</div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setSelectedAgent(null)}
                className="px-2.5 py-1 rounded border border-border text-xs text-sub hover:bg-white/5"
              >
                Close
              </button>
            </div>
          </div>

          <div className="text-xs text-sub mb-3">
            Showing latest traces from Langfuse API for this agent.
          </div>

          {tracesLoading && (
            <div className="mb-3 text-xs text-sub">Loading traces...</div>
          )}

          {!tracesLoading && agentTraces.length === 0 && (
            <div className="mb-3 p-3 rounded border border-border text-xs text-sub">
              No traces found for this agent yet.
            </div>
          )}

          {agentTraces.length > 0 && (
            <div className="overflow-x-auto border border-border rounded">
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr className="border-b border-border text-gray-500">
                    <th className="text-left py-2 px-3">Trace</th>
                    <th className="text-left py-2 px-3">Time</th>
                    <th className="text-right py-2 px-3">Turns</th>
                    <th className="text-right py-2 px-3">Latency</th>
                    <th className="text-right py-2 px-3">Cost</th>
                    <th className="text-left py-2 px-3">Session</th>
                    <th className="text-left py-2 px-3">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {agentTraces.map((trace) => (
                    <tr
                      key={trace.trace_id}
                      className={`border-b border-border/50 hover:bg-white/5 cursor-pointer ${
                        selectedTraceId === trace.trace_id ? 'bg-white/10' : ''
                      }`}
                      onClick={() => setSelectedTraceId(trace.trace_id)}
                    >
                      <td className="py-2 px-3 text-cyan">{trace.trace_id.slice(0, 8)}...</td>
                      <td className="py-2 px-3 text-gray-300">{trace.timestamp || '-'}</td>
                      <td className="py-2 px-3 text-right text-gray-300">{trace.turns > 0 ? trace.turns : '-'}</td>
                      <td className="py-2 px-3 text-right text-gray-300">{trace.latency_ms ? `${trace.latency_ms.toFixed(1)}ms` : '-'}</td>
                      <td className="py-2 px-3 text-right text-orange">{trace.cost ? `$${trace.cost.toFixed(4)}` : '-'}</td>
                      <td className="py-2 px-3 text-gray-400">{trace.session_id || '-'}</td>
                      <td className="py-2 px-3 text-gray-300">{trace.status || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {selectedTraceId && (
            <div className="mt-4 rounded border border-border p-3 space-y-3">
              <div className="flex items-center justify-between">
                <div className="text-sm font-mono text-white">Trace Detail</div>
                {traceDetailLoading && <div className="text-xs text-sub">Loading full trace...</div>}
              </div>

              {selectedTraceDetail?.error && (
                <div className="text-xs text-red">{selectedTraceDetail.error}</div>
              )}

              <div className="grid grid-cols-2 lg:grid-cols-5 gap-2 text-xs font-mono">
                <div><span className="text-gray-500">Source:</span> <span className="text-gray-300">{selectedTraceDetail?.source ?? '-'}</span></div>
                <div><span className="text-gray-500">Status:</span> <span className="text-gray-300">{selectedTraceDetail?.status ?? '-'}</span></div>
                <div><span className="text-gray-500">Turns:</span> <span className="text-gray-300">{typeof selectedTraceDetail?.turns === 'number' && selectedTraceDetail.turns > 0 ? selectedTraceDetail.turns : '-'}</span></div>
                <div><span className="text-gray-500">Latency:</span> <span className="text-gray-300">{typeof selectedTraceDetail?.latency_ms === 'number' ? `${selectedTraceDetail.latency_ms.toFixed(1)}ms` : '-'}</span></div>
                <div><span className="text-gray-500">Cost:</span> <span className="text-orange">{typeof selectedTraceDetail?.cost === 'number' ? `$${selectedTraceDetail.cost.toFixed(4)}` : '-'}</span></div>
              </div>

              <div className="rounded border border-border p-2">
                <div className="text-[10px] uppercase tracking-widest text-gray-500 mb-2">Input (Full)</div>
                <pre className="text-xs text-gray-300 whitespace-pre-wrap break-words max-h-64 overflow-auto">{pretty(selectedTraceDetail?.input)}</pre>
              </div>

              <div className="rounded border border-border p-2">
                <div className="text-[10px] uppercase tracking-widest text-gray-500 mb-2">Output (Full)</div>
                <pre className="text-xs text-gray-300 whitespace-pre-wrap break-words max-h-64 overflow-auto">{pretty(selectedTraceDetail?.output)}</pre>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                <div className="rounded border border-border p-2">
                  <div className="text-[10px] uppercase tracking-widest text-gray-500 mb-2">Metadata</div>
                  <pre className="text-xs text-gray-300 whitespace-pre-wrap break-words max-h-64 overflow-auto">{pretty(selectedTraceDetail?.metadata)}</pre>
                </div>
                <div className="rounded border border-border p-2">
                  <div className="text-[10px] uppercase tracking-widest text-gray-500 mb-2">Scores</div>
                  <pre className="text-xs text-gray-300 whitespace-pre-wrap break-words max-h-64 overflow-auto">{pretty(selectedTraceDetail?.scores)}</pre>
                </div>
              </div>

              <div className="rounded border border-border p-2">
                <div className="text-[10px] uppercase tracking-widest text-gray-500 mb-2">
                  Internal Reasoning Tree (Langfuse Observations)
                </div>
                {observationRows.length === 0 ? (
                  <div className="text-xs text-sub">No observation tree available for this trace.</div>
                ) : (
                  <div className="max-h-80 overflow-auto space-y-1">
                    {observationRows.map(({ node, depth }) => (
                      <details key={node.id} className="rounded border border-border/60 p-2">
                        <summary className="cursor-pointer text-xs font-mono text-gray-200">
                          <span style={{ paddingLeft: `${Math.max(0, depth) * 14}px` }}>
                            [{node.type || 'OBS'}] {node.name || node.id}
                          </span>
                        </summary>
                        <div className="mt-2 text-xs space-y-1">
                          <div className="text-gray-400">Level: {node.level || '-'}</div>
                          <div className="text-gray-400">Start: {node.start_time || '-'}</div>
                          <div className="text-gray-400">End: {node.end_time || '-'}</div>
                          <div className="text-gray-500">Input</div>
                          <pre className="text-xs text-gray-300 whitespace-pre-wrap break-words max-h-32 overflow-auto">{node.input_preview || '-'}</pre>
                          <div className="text-gray-500">Output</div>
                          <pre className="text-xs text-gray-300 whitespace-pre-wrap break-words max-h-32 overflow-auto">{node.output_preview || '-'}</pre>
                        </div>
                      </details>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
