import { useHallucinationRate, useHallucinationTrend } from '../../hooks/useDashboard'
import HorizontalBarChart from '../charts/HorizontalBarChart'
import MultiLineChart from '../charts/MultiLineChart'
import { fallbackHallucinationRates, fallbackHallucinationTrend } from '../../lib/chartFallbacks'
import { THEME } from '../../theme'

interface Props { paused: boolean }

// Static PII leakage table (sourced from metadata in future; hardcoded as demo structure)
const PII_SEVERITY_COLOR: Record<string, string> = {
  CRITICAL: THEME.red,
  HIGH: THEME.amber,
  MEDIUM: THEME.blue,
  LOW: THEME.green,
}

// Audit trail compliance items
const AUDIT_REGULATIONS = [
  { name: 'SOX', target: 95 },
  { name: 'GDPR', target: 95 },
  { name: 'MiFID II', target: 95 },
  { name: 'SEC 17a-4', target: 95 },
]

function AuditBar({ name, completeness, target }: { name: string; completeness: number; target: number }) {
  const color = completeness >= target ? THEME.green : completeness >= target - 10 ? THEME.amber : THEME.red
  return (
    <div className="flex items-center gap-3 py-2 border-b border-border/40 last:border-b-0">
      <span className="text-xs font-mono text-gray-300 w-20 shrink-0">{name}</span>
      <div className="flex-1 bg-border rounded-full h-1.5">
        <div
          className="h-1.5 rounded-full transition-all"
          style={{ width: `${completeness}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-xs font-mono shrink-0" style={{ color }}>{completeness}%</span>
    </div>
  )
}

export default function Compliance({ paused }: Props) {
  const { data: rawHalluRates = [] } = useHallucinationRate(paused)
  const { data: rawHalluTrend = [] } = useHallucinationTrend(paused)

  const halluRates = rawHalluRates.length > 0 ? rawHalluRates : fallbackHallucinationRates()
  const halluTrend = rawHalluTrend.length > 0 ? rawHalluTrend : fallbackHallucinationTrend()

  const halluBars = halluRates.map((d) => ({
    label: d.agent,
    value: d.hallucination_rate,
  }))
  const isSingleHallu = halluBars.length === 1
  const singleHallu = isSingleHallu ? halluBars[0] : null
  const halluPct = Math.max(0, Math.min(100, Number(singleHallu?.value ?? 0)))
  const halluSweep = `${(halluPct * 3.6).toFixed(1)}deg`

  const auditData = [
    { name: 'SOX', target: 95, completeness: 94 },
    { name: 'GDPR', target: 95, completeness: 93 },
    { name: 'MiFID II', target: 95, completeness: 95 },
    { name: 'SEC 17a-4', target: 95, completeness: 89 },
  ]

  // Current hallucination rate stats
  const currentRate = halluTrend.length ? halluTrend[halluTrend.length - 1]?.rate ?? 0 : 0
  const peakRate = halluTrend.length ? Math.max(...halluTrend.map((d) => d.rate)) : 0
  const belowThreshold = halluTrend.filter((d) => d.rate < 3).length

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* Hallucination rate by agent */}
      <div className="card">
        <div className="card-title">Hallucination Rate by Workflow</div>
        <div className="text-[10px] text-gray-500 mb-3">% responses containing ungrounded facts or numbers</div>
        {isSingleHallu && singleHallu ? (
          <div className="flex flex-col items-center">
            <div
              className="w-28 h-28 rounded-full grid place-items-center border border-border mb-3"
              style={{ background: `conic-gradient(${THEME.red} ${halluSweep}, #1e2433 0deg)` }}
            >
              <div className="w-20 h-20 rounded-full bg-[#0b1020] grid place-items-center border border-border">
                <div className={`text-lg font-semibold ${halluPct <= 3 ? 'text-green' : 'text-red'}`}>
                  {halluPct.toFixed(1)}%
                </div>
              </div>
            </div>
            <div className="text-sm text-cyan font-semibold mb-3">{singleHallu.label}</div>
            <div className="w-full grid grid-cols-2 gap-2 text-xs font-mono">
              <div className="rounded border border-border px-2 py-1.5 bg-[#0f1420]">
                <div className="text-gray-500">Threshold</div>
                <div className="text-amber font-semibold">3.0%</div>
              </div>
              <div className="rounded border border-border px-2 py-1.5 bg-[#0f1420]">
                <div className="text-gray-500">Status</div>
                <div className={`font-semibold ${halluPct <= 3 ? 'text-green' : 'text-red'}`}>
                  {halluPct <= 3 ? 'In Control' : 'Needs Attention'}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <HorizontalBarChart
            data={halluBars}
            color={THEME.red}
            unit="%"
            domain={[0, 8]}
            referenceLine={{ x: 3, label: '3% threshold' }}
          />
        )}
      </div>

      {/* Hallucination trend */}
      <div className="card">
        <div className="card-title">Hallucination Rate — Trend</div>
        <div className="text-[10px] text-gray-500 mb-3">Rolling 30-tick window vs. 3% threshold</div>
        <>
          <MultiLineChart
            data={halluTrend as unknown as Record<string, unknown>[]}
            lines={[{ key: 'rate', color: THEME.red, label: 'Halluc %' }]}
            referenceLine={{ y: 3, label: '3% SLO', color: THEME.amber }}
            yDomain={[0, 'auto']}
            unit="%"
            height={180}
          />
          <div className="flex gap-6 mt-3 text-xs font-mono">
            <div>
              <span className="text-gray-500">Current Rate</span>
              <div className="text-green font-semibold">{currentRate.toFixed(2)}%</div>
            </div>
            <div>
              <span className="text-gray-500">Peak (30 ticks)</span>
              <div className="text-red font-semibold">{peakRate.toFixed(2)}%</div>
            </div>
            <div>
              <span className="text-gray-500">Below Threshold</span>
              <div className="text-cyan font-semibold">{belowThreshold}/{halluTrend.length}</div>
            </div>
          </div>
        </>
      </div>

      {/* PII / Sensitive Data Leakage */}
      <div className="card">
        <div className="card-title">PII / Sensitive Data Leakage Events</div>
        <div className="text-[10px] text-gray-500 mb-3">Attempts to output restricted data without masking</div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs font-mono">
            <thead>
              <tr className="border-b border-border text-gray-500">
                <th className="text-left py-2 pr-3">Data Type</th>
                <th className="text-left py-2 pr-3">Severity</th>
                <th className="text-right py-2 pr-3">Count</th>
                <th className="text-right py-2 pr-3">Masked</th>
                <th className="text-left py-2">Workflow</th>
              </tr>
            </thead>
            <tbody>
              {[
                { type: 'Account Number', severity: 'CRITICAL', count: 8, masked: false, workflow: 'Portfolio' },
                { type: 'SSN', severity: 'CRITICAL', count: 2, masked: true, workflow: 'Client' },
                { type: 'Date of Birth', severity: 'HIGH', count: 7, masked: false, workflow: '10-K' },
                { type: 'Tax ID', severity: 'HIGH', count: 5, masked: false, workflow: 'Risk' },
                { type: 'Email', severity: 'MEDIUM', count: 3, masked: false, workflow: 'KYC' },
                { type: 'Phone', severity: 'LOW', count: 3, masked: true, workflow: 'Client' },
              ].map((row) => (
                <tr key={row.type} className="border-b border-border/50 hover:bg-white/5">
                  <td className="py-1.5 pr-3 text-gray-200">{row.type}</td>
                  <td className="py-1.5 pr-3">
                    <span
                      className="px-1.5 py-0.5 rounded text-[10px] font-semibold"
                      style={{
                        color: PII_SEVERITY_COLOR[row.severity],
                        border: `1px solid ${PII_SEVERITY_COLOR[row.severity]}44`,
                        backgroundColor: `${PII_SEVERITY_COLOR[row.severity]}11`,
                      }}
                    >
                      {row.severity}
                    </span>
                  </td>
                  <td className="py-1.5 pr-3 text-right text-gray-300">{row.count}</td>
                  <td className={`py-1.5 pr-3 text-right ${row.masked ? 'text-green' : 'text-red'}`}>
                    {row.masked ? '✓ Yes' : '✗ No'}
                  </td>
                  <td className="py-1.5 text-gray-400">{row.workflow}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Audit Trail Completeness */}
      <div className="card">
        <div className="card-title">Audit Trail Completeness</div>
        <div className="text-[10px] text-gray-500 mb-3">% agent actions fully logged with reasoning chain</div>
        <div className="space-y-1">
          {auditData.map((reg) => (
            <AuditBar key={reg.name} name={reg.name} completeness={reg.completeness} target={reg.target} />
          ))}
        </div>
        <div className="mt-3 text-[10px] text-gray-500 font-mono">
          Regulations monitored: SOX · GDPR · MiFID II · SEC 17a-4
        </div>
      </div>
    </div>
  )
}
