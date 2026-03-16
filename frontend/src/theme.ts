export const THEME = {
  bg: '#07080f',
  surface: '#0d1117',
  border: '#1e2433',
  dim: '#1a1f2e',
  text: '#e2e8f0',
  sub: '#7c8db0',
  green: '#10b981',
  red: '#ef4444',
  amber: '#f59e0b',
  blue: '#3b82f6',
  purple: '#8b5cf6',
  teal: '#14b8a6',
  cyan: '#06b6d4',
  p1: '#8b5cf6',
  p2: '#14b8a6',
  p3: '#f59e0b',
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
