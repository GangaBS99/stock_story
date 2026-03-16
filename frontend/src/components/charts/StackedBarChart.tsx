import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { chartTickStyle, chartTooltipStyle, THEME } from '../../theme'

interface BarConfig {
  key: string
  color: string
  label?: string
}

interface Props {
  data: Record<string, unknown>[]
  bars: BarConfig[]
  xKey?: string
  unit?: string
  height?: number
  layout?: 'horizontal' | 'vertical'
}

export default function StackedBarChart({
  data,
  bars,
  xKey = 'agent',
  unit = '',
  height = 200,
  layout = 'horizontal',
}: Props) {
  if (layout === 'vertical') {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <BarChart layout="vertical" data={data} margin={{ top: 4, right: 16, bottom: 0, left: 80 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} horizontal={false} />
          <XAxis
            type="number"
            tick={chartTickStyle}
            tickFormatter={(v) => `${v}${unit}`}
          />
          <YAxis
            type="category"
            dataKey={xKey}
            tick={chartTickStyle}
            width={80}
          />
          <Tooltip contentStyle={chartTooltipStyle} formatter={(v: number) => [`${v}${unit}`, '']} />
          <Legend wrapperStyle={{ fontSize: 10, fontFamily: 'SF Mono, Fira Code, monospace', color: THEME.sub }} />
          {bars.map((b) => (
            <Bar key={b.key} dataKey={b.key} stackId="a" fill={b.color} name={b.label ?? b.key} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 4, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
        <XAxis dataKey={xKey} tick={chartTickStyle} />
        <YAxis
          tick={chartTickStyle}
          tickFormatter={(v) => `${v}${unit}`}
        />
        <Tooltip contentStyle={chartTooltipStyle} formatter={(v: number) => [`${v}${unit}`, '']} />
        <Legend wrapperStyle={{ fontSize: 10, fontFamily: 'SF Mono, Fira Code, monospace', color: THEME.sub }} />
        {bars.map((b) => (
          <Bar key={b.key} dataKey={b.key} stackId="a" fill={b.color} name={b.label ?? b.key} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}
