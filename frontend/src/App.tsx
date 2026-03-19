import { useState, useEffect } from 'react'
import TopBar from './components/TopBar'
import Overview from './components/tabs/Overview'
import AgenticLogic from './components/tabs/AgenticLogic'
import Compliance from './components/tabs/Compliance'
import OperationalPerf from './components/tabs/OperationalPerf'
import PromptLibrary from './components/tabs/PromptLibrary'
import LangfuseRaw from './components/tabs/LangfuseRaw'
import { THEME } from './theme'

type Tab = 'overview' | 'agentic' | 'compliance' | 'operational' | 'prompts' | 'langfuse'

const TABS: { id: Tab; label: string; color: string }[] = [
  { id: 'overview', label: 'Overview', color: THEME.cyan },
  { id: 'agentic', label: 'Agentic Logic & Autonomy', color: THEME.p1 },
  { id: 'compliance', label: ' Accuracy & Compliance', color: THEME.p2 },
  { id: 'operational', label: 'Operational Performance', color: THEME.p3 },
  { id: 'prompts', label: 'Prompt Library', color: THEME.blue },
  { id: 'langfuse', label: 'Deep Evaluation', color: THEME.teal },
]

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('overview')
  const [paused, setPaused] = useState(false)
  const [clock, setClock] = useState(new Date().toLocaleTimeString('en-US', { hour12: false }))

  // Tick clock every second
  useEffect(() => {
    const t = setInterval(() => {
      setClock(new Date().toLocaleTimeString('en-US', { hour12: false }))
    }, 1000)
    return () => clearInterval(t)
  }, [])

  return (
    <div className="min-h-screen bg-bg font-sans text-text">
      <TopBar paused={paused} onTogglePause={() => setPaused((p) => !p)} />
      <div>
        <div className="bg-surface border-b border-border px-6">
          <nav className="flex gap-1 overflow-x-auto">
            {TABS.map((tab) => {
              const isActive = activeTab === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className="tab-btn whitespace-nowrap"
                  style={{
                    color: isActive ? tab.color : THEME.sub,
                    borderBottomColor: isActive ? tab.color : 'transparent',
                  }}
                >
                  {tab.label}
                </button>
              )
            })}
          </nav>
        </div>

        <main className="px-6 py-5 max-w-screen-2xl mx-auto">
          {paused && (
            <div className="mb-4 px-4 py-2 bg-yellow/10 border border-yellow/30 rounded text-yellow text-xs">
              ⏸ Live updates paused — click RESUME in the top bar to resume polling
            </div>
          )}

          {activeTab === 'overview' && <Overview paused={paused} />}
          {activeTab === 'agentic' && <AgenticLogic paused={paused} />}
          {activeTab === 'compliance' && <Compliance paused={paused} />}
          {activeTab === 'operational' && <OperationalPerf paused={paused} />}
          {activeTab === 'prompts' && <PromptLibrary paused={paused} />}
          {activeTab === 'langfuse' && <LangfuseRaw paused={paused} />}
        </main>

        <footer className="border-t border-border px-6 py-3 text-[11px] text-sub flex justify-between gap-4">
          <span>AgentOps · Financial Services Production</span>
          <span>
            {paused ? (
              <span className="text-yellow">⏸ Paused</span>
            ) : (
              <span className="text-green">● Live · {clock}</span>
            )}
          </span>
        </footer>
      </div>
    </div>
  )
}
