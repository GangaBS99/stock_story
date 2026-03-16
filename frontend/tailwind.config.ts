import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: '#07080f',
        surface: '#0d1117',
        border: '#1e2433',
        dim: '#1a1f2e',
        text: '#e2e8f0',
        sub: '#7c8db0',
        cyan: { DEFAULT: '#06b6d4', dim: '#0891b2' },
        green: { DEFAULT: '#10b981', dim: '#059669' },
        yellow: { DEFAULT: '#f59e0b', dim: '#d97706' },
        red: { DEFAULT: '#ef4444', dim: '#dc2626' },
        purple: { DEFAULT: '#8b5cf6', dim: '#7c3aed' },
        orange: { DEFAULT: '#f59e0b', dim: '#d97706' },
        p1: '#8b5cf6',
        p2: '#14b8a6',
        p3: '#f59e0b',
      },
      fontFamily: {
        mono: ['SF Mono', 'Fira Code', 'Consolas', 'monospace'],
        sans: ['SF Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
}

export default config
