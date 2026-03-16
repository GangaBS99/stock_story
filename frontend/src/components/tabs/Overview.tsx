import { useKPIs, useScoresTrend, useAgentsSummary } from '../../hooks/useDashboard'
import MultiLineChart from '../charts/MultiLineChart'
import { fallbackAgentsSummary, fallbackScoresTrend } from '../../lib/chartFallbacks'
import { THEME } from '../../theme'

interface Props { paused: boolean }

const SCORE_COLORS = [THEME.cyan, THEME.green, THEME.amber, THEME.purple, THEME.blue, THEME.red]

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
  const agents = rawAgents.length > 0 ? rawAgents : fallbackAgentsSummary()

  // Collect unique score keys from trend data
  const scoreKeys = trend.length
    ? Object.keys(trend[0]).filter((k) => k !== 'time')
    : []

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
          data={trend as Record<string, unknown>[]}
          lines={scoreKeys.map((k, i) => ({
            key: k,
            color: SCORE_COLORS[i % SCORE_COLORS.length],
            label: k,
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
                <th className="text-right py-2">P95 Lat</th>
              </tr>
            </thead>
            <tbody>
              {agents.map((a) => (
                <tr key={a.name} className="border-b border-border/50 hover:bg-white/5">
                  <td className="py-2 pr-4 text-white">{a.name}</td>
                  <td className="py-2 pr-4 text-gray-400">{a.framework}</td>
                  <td className="py-2 pr-4 text-right text-gray-300">{a.total_runs}</td>
                  <td className={`py-2 pr-4 text-right font-semibold ${
                    a.tsr >= 90 ? 'text-green' : a.tsr >= 70 ? 'text-yellow' : 'text-red'
                  }`}>{a.tsr}%</td>
                  <td className="py-2 pr-4 text-right text-gray-300">{a.avg_latency_ms}ms</td>
                  <td className="py-2 text-right text-gray-300">{a.p95_latency_ms}ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
