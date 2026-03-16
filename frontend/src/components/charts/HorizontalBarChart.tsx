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

interface Props {
  data: { label: string; value: number }[]
  color?: string
  unit?: string
  referenceLine?: { x: number; label: string }
  height?: number
  domain?: [number, number]
}

function getBarColor(value: number, unit: string): string {
  if (unit === '%') {
    if (value >= 90) return THEME.green
    if (value >= 70) return THEME.amber
    return THEME.red
  }
  return THEME.cyan
}

export default function HorizontalBarChart({
  data,
  color,
  unit = '%',
  referenceLine,
  height,
  domain = [0, 100],
}: Props) {
  const h = height ?? Math.max(120, data.length * 36)

  return (
    <ResponsiveContainer width="100%" height={h}>
      <BarChart layout="vertical" data={data} margin={{ top: 4, right: 24, bottom: 0, left: 100 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} horizontal={false} />
        <XAxis
          type="number"
          domain={domain}
          tick={chartTickStyle}
          tickFormatter={(v) => `${v}${unit}`}
        />
        <YAxis
          type="category"
          dataKey="label"
          tick={{ ...chartTickStyle, fontSize: 11 }}
          width={100}
        />
        <Tooltip
          contentStyle={chartTooltipStyle}
          formatter={(v: number) => [`${v}${unit}`, '']}
        />
        {referenceLine && (
          <ReferenceLine
            x={referenceLine.x}
            stroke={THEME.red}
            strokeDasharray="4 2"
            label={{ value: referenceLine.label, fill: THEME.red, fontSize: 9 }}
          />
        )}
        <Bar dataKey="value" radius={[0, 3, 3, 0]}>
          {data.map((entry, i) => (
            <Cell key={i} fill={color ?? getBarColor(entry.value, unit)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
