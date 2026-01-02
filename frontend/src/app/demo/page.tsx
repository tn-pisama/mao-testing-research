'use client'

import { useState, useEffect } from 'react'
import { Layout } from '@/components/common/Layout'
import { AgentCard, AgentOrchestrationView, AgentActivityFeed, AgentMetricsPanel } from '@/components/agents'
import { DemoControlsPanel } from '@/components/demo/DemoControlsPanel'
import { DemoScenarioSelector } from '@/components/demo/DemoScenarioSelector'
import { LiveDetectionFeed } from '@/components/demo/LiveDetectionFeed'
import { LoopVisualization } from '@/components/demo/LoopVisualization'
import { useDemoMode } from '@/hooks/useDemoMode'
import { Button } from '@/components/ui/Button'
import { Play, RotateCcw, Sparkles, AlertTriangle, TrendingUp } from 'lucide-react'

type DemoScenario = 'healthy' | 'loop' | 'corruption' | 'deadlock'

const scenarios: Record<DemoScenario, { title: string; description: string; icon: typeof Play }> = {
  healthy: {
    title: 'Healthy Workflow',
    description: 'Normal multi-agent execution with no issues',
    icon: TrendingUp,
  },
  loop: {
    title: 'Infinite Loop',
    description: 'Agents stuck in repetitive behavior pattern',
    icon: RotateCcw,
  },
  corruption: {
    title: 'State Corruption',
    description: 'Semantic drift detected in agent state',
    icon: AlertTriangle,
  },
  deadlock: {
    title: 'Coordination Deadlock',
    description: 'Agents waiting on each other indefinitely',
    icon: AlertTriangle,
  },
}

export default function DemoPage() {
  const [activeScenario, setActiveScenario] = useState<DemoScenario>('healthy')
  const [demoStep, setDemoStep] = useState(0)
  const [showDetection, setShowDetection] = useState(false)
  const demo = useDemoMode({ autoSimulate: false })

  useEffect(() => {
    if (demo.isSimulating && activeScenario !== 'healthy') {
      const timer = setTimeout(() => {
        setShowDetection(true)
      }, 5000)
      return () => clearTimeout(timer)
    } else {
      setShowDetection(false)
    }
  }, [demo.isSimulating, activeScenario])

  const handleScenarioChange = (scenario: DemoScenario) => {
    setActiveScenario(scenario)
    setShowDetection(false)
    setDemoStep(0)
    demo.refreshData()
  }

  const handleStartDemo = () => {
    setDemoStep(1)
    demo.startSimulation()
  }

  const handleResetDemo = () => {
    setDemoStep(0)
    setShowDetection(false)
    demo.stopSimulation()
    demo.refreshData()
  }

  if (!demo.isLoaded) {
    return (
      <Layout>
        <div className="p-6">
          <div className="animate-pulse space-y-6">
            <div className="h-10 w-64 bg-slate-700 rounded" />
            <div className="grid grid-cols-4 gap-4">
              {[1,2,3,4].map(i => <div key={i} className="h-32 bg-slate-700 rounded-xl" />)}
            </div>
          </div>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="p-6">
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-gradient-to-br from-purple-500/20 to-pink-500/20 border border-purple-500/30">
              <Sparkles size={24} className="text-purple-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Interactive Demo</h1>
              <p className="text-sm text-slate-400">
                Experience real-time multi-agent failure detection
              </p>
            </div>
          </div>
        </div>

        <div className="grid lg:grid-cols-4 gap-6 mb-6">
          <DemoScenarioSelector
            scenarios={scenarios}
            activeScenario={activeScenario}
            onSelectScenario={handleScenarioChange}
          />
        </div>

        <div className="flex items-center gap-4 mb-6">
          {demoStep === 0 ? (
            <Button onClick={handleStartDemo} leftIcon={<Play size={16} />} size="lg">
              Start Demo
            </Button>
          ) : (
            <>
              <DemoControlsPanel
                isSimulating={demo.isSimulating}
                onToggleSimulation={demo.toggleSimulation}
                onRefresh={handleResetDemo}
              />
              <Button onClick={handleResetDemo} variant="secondary" leftIcon={<RotateCcw size={16} />}>
                Reset
              </Button>
            </>
          )}

          {demoStep > 0 && (
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-800/50 border border-slate-700">
              <span className="text-sm text-slate-400">Scenario:</span>
              <span className="text-sm font-medium text-white">{scenarios[activeScenario].title}</span>
            </div>
          )}
        </div>

        {demoStep > 0 && (
          <>
            <AgentMetricsPanel metrics={demo.agentMetrics} />

            <div className="mt-6 grid lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2">
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-white">Agent Orchestration</h2>
                  {showDetection && (
                    <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-red-500/20 border border-red-500/30 animate-pulse">
                      <AlertTriangle size={14} className="text-red-400" />
                      <span className="text-xs font-medium text-red-400">Issue Detected</span>
                    </div>
                  )}
                </div>
                
                {activeScenario === 'loop' && showDetection ? (
                  <LoopVisualization agents={demo.agents} />
                ) : (
                  <AgentOrchestrationView
                    agents={demo.agents}
                    messages={demo.messages}
                  />
                )}
              </div>

              <div className="space-y-6">
                {showDetection && (
                  <LiveDetectionFeed
                    scenario={activeScenario}
                    isActive={demo.isSimulating}
                  />
                )}
                <AgentActivityFeed
                  events={demo.activityEvents}
                  isLive={demo.isSimulating}
                  maxHeight={showDetection ? '300px' : '560px'}
                />
              </div>
            </div>
          </>
        )}

        {demoStep === 0 && (
          <div className="mt-8 p-8 rounded-2xl border border-slate-700 bg-gradient-to-br from-slate-800/50 to-slate-900/50 text-center">
            <div className="max-w-md mx-auto">
              <div className="p-4 rounded-full bg-slate-800 border border-slate-700 w-16 h-16 mx-auto mb-4 flex items-center justify-center">
                <Play size={24} className="text-primary-400" />
              </div>
              <h3 className="text-xl font-semibold text-white mb-2">Ready to Demo</h3>
              <p className="text-slate-400 mb-6">
                Select a scenario above and click Start Demo to see PISAMA in action.
                Watch as agents execute, metrics update in real-time, and failures are detected.
              </p>
              <Button onClick={handleStartDemo} size="lg" leftIcon={<Play size={16} />}>
                Start Demo
              </Button>
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}
