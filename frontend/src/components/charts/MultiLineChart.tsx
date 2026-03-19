import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import { chartTickStyle, chartTooltipStyle, THEME } from '../../theme'

interface LineConfig {
  key: string
  color: string
  label?: string
}

interface Props {
  data: Record<string, unknown>[]
  lines: LineConfig[]
  xKey?: string
  referenceLine?: { y: number; label: string; color?: string }
  yDomain?: [number | 'auto', number | 'auto']
  unit?: string
  height?: number
}

function formatNumeric(value: unknown): string {
  const n = Number(value)
  if (!Number.isFinite(n)) return '-'
  if (Math.abs(n) >= 100) return n.toFixed(0)
  if (Math.abs(n) >= 10) return n.toFixed(1)
  return n.toFixed(2)
}

export default function MultiLineChart({
  data,
  lines,
  xKey = 'time',
  referenceLine,
  yDomain,
  unit = '',
  height = 200,
}: Props) {
  const showDots = data.length <= 12

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 4, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
        <XAxis dataKey={xKey} tick={chartTickStyle} />
        <YAxis
          domain={yDomain}
          tick={chartTickStyle}
          tickFormatter={(v) => `${formatNumeric(v)}${unit}`}
        />
        <Tooltip
          contentStyle={chartTooltipStyle}
          labelStyle={{ color: THEME.sub }}
          formatter={(v: number, name: string) => [`${formatNumeric(v)}${unit}`, name]}
        />
        <Legend
          wrapperStyle={{ fontSize: 10, fontFamily: 'SF Mono, Fira Code, monospace', color: THEME.sub }}
        />
        {referenceLine && (
          <ReferenceLine
            y={referenceLine.y}
            stroke={referenceLine.color ?? '#ff4444'}
            strokeDasharray="4 2"
            label={{ value: referenceLine.label, fill: referenceLine.color ?? '#ff4444', fontSize: 9 }}
          />
        )}
        {lines.map((l) => (
          <Line
            key={l.key}
            type="monotone"
            dataKey={l.key}
            stroke={l.color}
            strokeWidth={2}
            dot={showDots}
            name={l.label ?? l.key}
            activeDot={{ r: 4 }}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}
