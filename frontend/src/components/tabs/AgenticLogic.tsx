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
  const isSingleTSR = tsrBars.length === 1
  const isSingleTool = toolBars.length === 1
  const isSingleTurns = turnsBars.length === 1
  const singleTSR = isSingleTSR ? tsrBars[0] : null
  const singleTool = isSingleTool ? toolBars[0] : null
  const singleTurn = isSingleTurns ? turnsBars[0] : null

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
        {isSingleTSR && singleTSR ? (
          <div className="space-y-3">
            <div className="flex items-end justify-between">
              <div>
                <div className="text-[10px] text-gray-500 uppercase tracking-wide">Workflow</div>
                <div className="text-cyan text-sm font-semibold">{singleTSR.label}</div>
              </div>
              <div className={`text-2xl font-semibold ${singleTSR.value >= 95 ? 'text-green' : 'text-yellow'}`}>
                {singleTSR.value.toFixed(1)}%
              </div>
            </div>
            <div className="h-3 rounded-full bg-border overflow-hidden">
              <div
                className={`h-3 rounded-full ${singleTSR.value >= 95 ? 'bg-green' : 'bg-yellow'}`}
                style={{ width: `${Math.max(0, Math.min(100, singleTSR.value))}%` }}
              />
            </div>
            <div className="text-xs font-mono text-gray-400">
              {singleTSR.value >= 95 ? 'Healthy autonomous completion' : 'Below desired autonomy band'}
            </div>
          </div>
        ) : (
          <HorizontalBarChart data={tsrBars} unit="%" domain={[0, 100]} />
        )}
      </div>

      {/* Tool selection accuracy */}
      <div className="card">
        <div className="card-title">Tool Selection Accuracy</div>
        <div className="text-[10px] text-gray-500 mb-3">Correct API called with right parameters</div>
        {isSingleTool && singleTool ? (
          <div className="space-y-3">
            <div className="flex items-end justify-between">
              <div>
                <div className="text-[10px] text-gray-500 uppercase tracking-wide">Workflow</div>
                <div className="text-cyan text-sm font-semibold">{singleTool.label}</div>
              </div>
              <div className={`text-2xl font-semibold ${singleTool.value >= 90 ? 'text-green' : 'text-red'}`}>
                {singleTool.value.toFixed(1)}%
              </div>
            </div>
            <div className="h-3 rounded-full bg-border overflow-hidden">
              <div
                className={`h-3 rounded-full ${singleTool.value >= 90 ? 'bg-green' : 'bg-red'}`}
                style={{ width: `${Math.max(0, Math.min(100, singleTool.value))}%` }}
              />
            </div>
            <div className="text-xs font-mono text-gray-400">
              Target: 90% routing accuracy
            </div>
          </div>
        ) : (
          <HorizontalBarChart
            data={toolBars}
            unit="%"
            domain={[70, 100]}
            referenceLine={{ x: 90, label: '90% target' }}
          />
        )}
      </div>

      {/* Decision turn count */}
      <div className="card">
        <div className="card-title">Decision Turn Count</div>
        <div className="text-[10px] text-gray-500 mb-3">Spike above 12 turns indicates reasoning loop</div>
        {isSingleTurns && singleTurn ? (
          <div className="space-y-3">
            <div className="flex items-end justify-between">
              <div>
                <div className="text-[10px] text-gray-500 uppercase tracking-wide">Workflow</div>
                <div className="text-cyan text-sm font-semibold">{singleTurn.agent}</div>
              </div>
              <div className={`text-2xl font-semibold ${singleTurn.avg_turns > 12 ? 'text-red' : 'text-purple'}`}>
                {singleTurn.avg_turns.toFixed(1)}
              </div>
            </div>
            <div className="h-3 rounded-full bg-border overflow-hidden">
              <div
                className={`h-3 rounded-full ${singleTurn.avg_turns > 12 ? 'bg-red' : 'bg-purple'}`}
                style={{ width: `${Math.max(5, Math.min(100, (singleTurn.avg_turns / 20) * 100))}%` }}
              />
            </div>
            <div className="text-xs font-mono text-gray-400">
              Loop threshold: 12 turns · Loops today: {singleTurn.loops}
            </div>
          </div>
        ) : (
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
        )}
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
