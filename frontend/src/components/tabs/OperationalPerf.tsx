import {
  useLatencyBreakdown,
  useLatencyPercentiles,
  useTokenCost,
  useErrorRecovery,
} from '../../hooks/useDashboard'
import StackedBarChart from '../charts/StackedBarChart'
import MultiLineChart from '../charts/MultiLineChart'
import ComboChart from '../charts/ComboChart'
import HorizontalBarChart from '../charts/HorizontalBarChart'
import {
  fallbackLatencyBreakdown,
  fallbackLatencyPercentiles,
  fallbackTokenCost,
  fallbackErrorRecovery,
} from '../../lib/chartFallbacks'

interface Props { paused: boolean }

const LATENCY_BARS = [
  { key: 'prompt', color: '#00e5ff', label: 'Prompt Processing' },
  { key: 'tool_call', color: '#00ff88', label: 'Tool Call' },
  { key: 'synthesis', color: '#ffd600', label: 'Synthesis' },
  { key: 'output', color: '#bf5af2', label: 'Output' },
]

export default function OperationalPerf({ paused }: Props) {
  const { data: rawBreakdown = [] } = useLatencyBreakdown(paused)
  const { data: rawPercentiles = [] } = useLatencyPercentiles(paused)
  const { data: rawTokenCost = [] } = useTokenCost(paused)
  const { data: rawErrorRecovery = [] } = useErrorRecovery(paused)

  const breakdown = rawBreakdown.length > 0 ? rawBreakdown : fallbackLatencyBreakdown()
  const percentiles = rawPercentiles.length > 0 ? rawPercentiles : fallbackLatencyPercentiles()
  const tokenCost = rawTokenCost.length > 0 ? rawTokenCost : fallbackTokenCost()
  const errorRecovery = rawErrorRecovery.length > 0 ? rawErrorRecovery : fallbackErrorRecovery()

  const recoveryBars = errorRecovery.map((d) => ({
    label: d.agent,
    value: d.recovery_rate,
  }))

  const avgRecovery = errorRecovery.length
    ? Math.round(errorRecovery.reduce((s, d) => s + d.recovery_rate, 0) / errorRecovery.length)
    : 0
  const totalRetries = errorRecovery.reduce((s, d) => s + d.total_retries, 0)
  const sessionCrashes = errorRecovery.reduce((s, d) => s + d.session_crashes, 0)

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* Latency step breakdown */}
      <div className="card">
        <div className="card-title">Latency Per Agent Loop — Step Breakdown</div>
        <div className="text-[10px] text-gray-500 mb-3">
          Prompt Processing → Tool Call → Synthesis → Output (ms)
        </div>
        <StackedBarChart
          data={breakdown as unknown as Record<string, unknown>[]}
          bars={LATENCY_BARS}
          xKey="agent"
          unit="ms"
          height={220}
        />
      </div>

      {/* P50/P95/P99 latency trend */}
      <div className="card">
        <div className="card-title">P50 / P95 / P99 Latency Trend</div>
        <div className="text-[10px] text-gray-500 mb-3">End-to-end response time percentiles (ms)</div>
        <MultiLineChart
          data={percentiles as unknown as Record<string, unknown>[]}
          lines={[
            { key: 'p50', color: '#10b981', label: 'P50' },
            { key: 'p95', color: '#f59e0b', label: 'P95' },
            { key: 'p99', color: '#ef4444', label: 'P99' },
          ]}
          referenceLine={{ y: 1500, label: '1500ms SLO', color: '#ef4444' }}
          unit="ms"
          height={220}
        />
      </div>

      {/* Token throughput & cost */}
      <div className="card">
        <div className="card-title">Token Throughput & Cost Per Task</div>
        <div className="text-[10px] text-gray-500 mb-3">$0.50 per complete agent workflow vs. 30-tick trend</div>
        <ComboChart
          data={tokenCost as unknown as Record<string, unknown>[]}
          barKey="tokens"
          lineKey="cost"
          barColor="#3b82f6"
          lineColor="#f59e0b"
          barLabel="Tokens"
          lineLabel="Cost ($)"
          leftUnit=""
          rightUnit="$"
          height={220}
        />
      </div>

      {/* Error recovery rate */}
      <div className="card">
        <div className="card-title">Error Recovery Rate</div>
        <div className="text-[10px] text-gray-500 mb-3">
          % API/tool failures navigated via retry or fallback (no crash)
        </div>
        <>
          <HorizontalBarChart
            data={recoveryBars}
            unit="%"
            domain={[0, 100]}
            referenceLine={{ x: 85, label: '85% min' }}
          />
          <div className="flex gap-6 mt-3 text-xs font-mono">
            <div>
              <div className="text-gray-500">Avg Recovery</div>
              <div className={`font-semibold ${avgRecovery >= 85 ? 'text-green' : 'text-yellow'}`}>
                {avgRecovery}%
              </div>
            </div>
            <div>
              <div className="text-gray-500">Total Retries</div>
              <div className="text-yellow font-semibold">{totalRetries}</div>
            </div>
            <div>
              <div className="text-gray-500">Session Crashes</div>
              <div className="text-red font-semibold">{sessionCrashes}</div>
            </div>
          </div>
        </>
      </div>
    </div>
  )
}
