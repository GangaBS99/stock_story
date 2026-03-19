export const THEME = {
  bg: '#0b1020',
  surface: '#111827',
  border: '#273244',
  dim: '#0f172a',
  text: '#e5e7eb',
  sub: '#94a3b8',
  green: '#22c55e',
  red: '#ef4444',
  amber: '#f59e0b',
  blue: '#3b82f6',
  purple: '#a78bfa',
  teal: '#14b8a6',
  cyan: '#22d3ee',
  p1: '#a78bfa',
  p2: '#22d3ee',
  p3: '#34d399',
} as const

export const chartTickStyle = {
  fill: THEME.sub,
  fontSize: 10,
  fontFamily: 'SF Mono, Fira Code, monospace',
}

export const chartTooltipStyle = {
  backgroundColor: THEME.dim,
  border: `1px solid ${THEME.border}`,
  borderRadius: 6,
  fontSize: 11,
  fontFamily: 'SF Mono, Fira Code, monospace',
  color: THEME.text,
}
