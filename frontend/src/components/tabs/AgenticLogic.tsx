import {
  useTSRByAgent,
  useToolAccuracy,
  useDecisionTurns,
  useScoresTrend,
} from '../../hooks/useDashboard'
import HorizontalBarChart from '../charts/HorizontalBarChart'
import MultiLineChart from '../charts/MultiLineChart'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { chartTickStyle, chartTooltipStyle, THEME } from '../../theme'
import {
  fallbackTSRByAgent,
  fallbackToolAccuracy,
  fallbackDecisionTurns,
} from '../../lib/chartFallbacks'

interface Props { paused: boolean }

function EmptyState({ msg }: { msg: string }) {
  return (
    <div className="flex items-center justify-center h-24 text-gray-500 text-sm font-mono">{msg}</div>
  )
}

export default function AgenticLogic({ paused }: Props) {
  const { data: rawTsrData = [] } = useTSRByAgent(paused)
  const { data: rawToolData = [] } = useToolAccuracy(paused)
  const { data: rawTurnsData = [] } = useDecisionTurns(paused)
  const { data: scoreTrend = [] } = useScoresTrend(paused)

  const tsrData = rawTsrData.length > 0 ? rawTsrData : fallbackTSRByAgent()
  const toolData = rawToolData.length > 0 ? rawToolData : fallbackToolAccuracy()
  const turnsData = rawTurnsData.length > 0 ? rawTurnsData : fallbackDecisionTurns()

  const tsrBars = tsrData.map((d) => ({ label: d.agent, value: d.tsr }))
  const toolBars = toolData.map((d) => ({ label: d.tool, value: d.accuracy }))
  const turnsBars = turnsData.map((d) => ({
    agent: d.agent,
    avg_turns: d.avg_turns,
    loops: d.loops_detected,
  }))

  // Context utilization: use helpfulness/accuracy scores as proxy
  const ctxKeys = scoreTrend.length
    ? Object.keys(scoreTrend[0]).filter((k) => k !== 'time' && ['helpfulness', 'accuracy', 'relevance'].includes(k))
    : []
  const ctxColors: Record<string, string> = {
    helpfulness: THEME.green,
    accuracy: THEME.cyan,
    relevance: THEME.purple,
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* TSR by workflow */}
      <div className="card">
        <div className="card-title">Task Success Rate (TSR) by Workflow</div>
        <div className="text-[10px] text-gray-500 mb-3">% tasks completed without human intervention</div>
        <HorizontalBarChart data={tsrBars} unit="%" domain={[0, 100]} />
      </div>

      {/* Tool selection accuracy */}
      <div className="card">
        <div className="card-title">Tool Selection Accuracy</div>
        <div className="text-[10px] text-gray-500 mb-3">Correct API called with right parameters</div>
        <HorizontalBarChart
          data={toolBars}
          unit="%"
          domain={[70, 100]}
          referenceLine={{ x: 90, label: '90% target' }}
        />
      </div>

      {/* Decision turn count */}
      <div className="card">
        <div className="card-title">Decision Turn Count</div>
        <div className="text-[10px] text-gray-500 mb-3">Spike above 12 turns indicates reasoning loop</div>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={turnsBars} margin={{ top: 4, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
            <XAxis dataKey="agent" tick={chartTickStyle} />
            <YAxis tick={chartTickStyle} />
            <Tooltip contentStyle={chartTooltipStyle} />
            <ReferenceLine y={12} stroke={THEME.red} strokeDasharray="4 2"
              label={{ value: 'Loop Detected (12)', fill: THEME.red, fontSize: 9 }} />
            <Bar dataKey="avg_turns" name="Avg Turns" radius={[3, 3, 0, 0]}>
              {turnsBars.map((entry, i) => (
                <Cell key={i} fill={entry.avg_turns > 12 ? THEME.red : THEME.purple} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        {turnsData.some((d) => d.loops_detected > 0) && (
          <div className="mt-2 text-xs font-mono text-red">
            ⚠ Loops today: {turnsData.reduce((s, d) => s + d.loops_detected, 0)}
          </div>
        )}
      </div>

      {/* Context utilization score */}
      <div className="card">
        <div className="card-title">Context Utilization Score</div>
        <div className="text-[10px] text-gray-500 mb-3">Long-term memory vs. prompt-only reasoning</div>
        {ctxKeys.length === 0 || scoreTrend.length === 0 ? (
          <EmptyState msg="No helpfulness / accuracy scores yet" />
        ) : (
          <MultiLineChart
            data={scoreTrend as Record<string, unknown>[]}
            lines={ctxKeys.map((k) => ({
              key: k,
              color: ctxColors[k] ?? '#00e5ff',
              label: k,
            }))}
            yDomain={[0, 1]}
            height={200}
          />
        )}
      </div>
    </div>
  )
}
