import { useKPIs } from '../hooks/useDashboard'
import { THEME } from '../theme'

interface TopBarProps {
  paused: boolean
  onTogglePause: () => void
}

interface KpiChipProps {
  label: string
  value: string | number
  color?: string
  pulse?: boolean
}

function KpiChip({ label, value, color = 'text-cyan', pulse }: KpiChipProps) {
  return (
    <div className="text-center">
      <span className={`text-sm font-semibold ${color} ${pulse ? 'animate-pulse' : ''}`}>
        {value}
      </span>
      <span className="block text-[10px] text-sub mt-0.5">{label}</span>
    </div>
  )
}

export default function TopBar({ paused, onTogglePause }: TopBarProps) {
  const { data: kpis, isError } = useKPIs(paused)

  const tsr = kpis?.tsr ?? '—'
  const toolAcc = kpis?.tool_accuracy ?? '—'
  const halluc = kpis?.hallucination_rate ?? '—'
  const hitl = kpis?.hitl_count ?? '—'
  const p95 = kpis?.p95_latency_ms ? `${kpis.p95_latency_ms}ms` : '—'
  const cost = kpis?.avg_cost_per_task ? `$${kpis.avg_cost_per_task}` : '$0.00'

  const tsrColor =
    typeof kpis?.tsr === 'number'
      ? kpis.tsr >= 90
        ? 'text-green'
        : kpis.tsr >= 70
        ? 'text-yellow'
        : 'text-red'
      : 'text-gray-400'

  const hallucColor =
    typeof kpis?.hallucination_rate === 'number'
      ? kpis.hallucination_rate < 3
        ? 'text-green'
        : kpis.hallucination_rate < 7
        ? 'text-yellow'
        : 'text-red'
      : 'text-gray-400'

  return (
    <header className="bg-surface border-b border-border px-6 py-3 flex items-center justify-between gap-6">
      <div className="flex items-center gap-3 min-w-[220px]">
        <div
          className={`w-2 h-2 rounded-full ${paused ? 'bg-yellow' : 'bg-green'}`}
          style={{ boxShadow: `0 0 8px ${paused ? THEME.amber : THEME.green}` }}
        />
        <div>
          <div className="text-base font-semibold text-text leading-none tracking-wide">AgentOps Dashboard</div>
          <div className="text-[10px] text-sub leading-none mt-1">
            <span className="px-2 py-0.5 bg-dim rounded">Financial Services · Prod</span>
          </div>
        </div>
      </div>

      <div className="flex flex-1 items-center justify-end gap-5">
        <KpiChip label="TSR" value={typeof tsr === 'number' ? `${tsr}%` : tsr} color={tsrColor} />
        <KpiChip label="Tool Acc" value={typeof toolAcc === 'number' ? `${toolAcc}%` : toolAcc} color="text-purple" />
        <KpiChip label="Halluc" value={typeof halluc === 'number' ? `${halluc}%` : halluc} color={hallucColor} pulse={typeof kpis?.hallucination_rate === 'number' && kpis.hallucination_rate > 5} />
        <KpiChip label="HITL Q" value={hitl} color="text-cyan" />
        <KpiChip label="P95 Lat" value={p95} color="text-yellow" />
        <KpiChip label="$/Task" value={cost} color="text-orange" />
        <button
          onClick={onTogglePause}
          className={`px-3 py-1 rounded text-xs font-semibold border transition-colors ${
            paused
              ? 'bg-yellow/10 border-yellow text-yellow hover:bg-yellow/20'
              : 'bg-green/10 border-green text-green hover:bg-green/20'
          }`}
        >
          {paused ? '▶ Resume' : '⏸ Pause'}
        </button>
        <div className="text-xs text-sub">
          {new Date().toLocaleTimeString('en-US', { hour12: false })}
        </div>
      </div>

      {isError && (
        <div className="text-xs text-red">⚠ API unreachable</div>
      )}
    </header>
  )
}
