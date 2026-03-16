import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { chartTickStyle, chartTooltipStyle, THEME } from '../../theme'

interface Props {
  data: Record<string, unknown>[]
  barKey: string
  lineKey: string
  xKey?: string
  barColor?: string
  lineColor?: string
  barLabel?: string
  lineLabel?: string
  leftUnit?: string
  rightUnit?: string
  height?: number
}

export default function ComboChart({
  data,
  barKey,
  lineKey,
  xKey = 'time',
  barColor = THEME.blue,
  lineColor = THEME.amber,
  barLabel,
  lineLabel,
  leftUnit = '',
  rightUnit = '',
  height = 200,
}: Props) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 4, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={THEME.border} />
        <XAxis dataKey={xKey} tick={chartTickStyle} />
        <YAxis
          yAxisId="left"
          tick={chartTickStyle}
          tickFormatter={(v) => `${v}${leftUnit}`}
        />
        <YAxis
          yAxisId="right"
          orientation="right"
          tick={chartTickStyle}
          tickFormatter={(v) => `${rightUnit}${v}`}
        />
        <Tooltip
          contentStyle={chartTooltipStyle}
          labelStyle={{ color: THEME.sub }}
        />
        <Legend wrapperStyle={{ fontSize: 10, fontFamily: 'SF Mono, Fira Code, monospace', color: THEME.sub }} />
        <Bar
          yAxisId="left"
          dataKey={barKey}
          fill={barColor}
          fillOpacity={0.7}
          name={barLabel ?? barKey}
        />
        <Line
          yAxisId="right"
          type="monotone"
          dataKey={lineKey}
          stroke={lineColor}
          strokeWidth={2}
          dot={false}
          name={lineLabel ?? lineKey}
        />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
