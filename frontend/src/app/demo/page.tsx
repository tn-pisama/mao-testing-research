'use client'

export const dynamic = 'force-dynamic'

import { useState, useEffect } from 'react'
import { Layout } from '@/components/common/Layout'
import { AgentMetricsPanel } from '@/components/agents'
import { DemoControlsPanel } from '@/components/demo/DemoControlsPanel'
import { DemoScenarioSelector } from '@/components/demo/DemoScenarioSelector'
import { LiveDetectionFeed } from '@/components/demo/LiveDetectionFeed'
import { LoopVisualization } from '@/components/demo/LoopVisualization'
import { GuidedWalkthrough, WalkthroughTrigger } from '@/components/demo/GuidedWalkthrough'
import { TraceUpload } from '@/components/demo/TraceUpload'
import { allDemoScenarios, getDemoScenario } from '@/lib/demo-fixtures'
import type { DemoScenario } from '@/lib/demo-fixtures'
import { useDemoMode } from '@/hooks/useDemoMode'
import { Button } from '@/components/ui/Button'
import { Play, RotateCcw, Sparkles, AlertTriangle, Link } from 'lucide-react'

export default function DemoPage() {
  const [activeScenarioId, setActiveScenarioId] = useState<string>(allDemoScenarios[0]?.id || '')
  const [demoStep, setDemoStep] = useState(0)
  const [showWalkthrough, setShowWalkthrough] = useState(false)
  const [hasSeenTour, setHasSeenTour] = useState(false)
  const demo = useDemoMode({ autoSimulate: false })

  const activeScenario: DemoScenario | undefined = getDemoScenario(activeScenarioId)
  const hasDetections = (activeScenario?.detections.length ?? 0) > 0

  useEffect(() => {
    const seen = localStorage.getItem('pisama_demo_tour_seen')
    if (!seen) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time initialization from localStorage
      setShowWalkthrough(true)
    } else {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time initialization from localStorage
      setHasSeenTour(true)
    }
  }, [])

  const handleScenarioChange = (id: string) => {
    setActiveScenarioId(id)
    setDemoStep(0)
    demo.stopSimulation()
  }

  const handleStartDemo = () => {
    setDemoStep(1)
    demo.startSimulation()
  }

  const handleResetDemo = () => {
    setDemoStep(0)
    demo.stopSimulation()
    demo.refreshData()
  }

  const handleWalkthroughComplete = () => {
    localStorage.setItem('pisama_demo_tour_seen', 'true')
    setShowWalkthrough(false)
    setHasSeenTour(true)
  }

  const handleWalkthroughSkip = () => {
    localStorage.setItem('pisama_demo_tour_seen', 'true')
    setShowWalkthrough(false)
    setHasSeenTour(true)
  }

  if (!demo.isLoaded) {
    return (
      <Layout>
        <div className="p-6">
          <div className="animate-pulse space-y-6">
            <div className="h-10 w-64 bg-zinc-700 rounded" />
            <div className="grid grid-cols-5 gap-3">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="h-28 bg-zinc-700 rounded-xl" />
              ))}
            </div>
          </div>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      {showWalkthrough && (
        <GuidedWalkthrough
          onComplete={handleWalkthroughComplete}
          onSkip={handleWalkthroughSkip}
        />
      )}

      <div className="p-6">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 rounded-lg bg-gradient-to-br from-purple-500/20 to-pink-500/20 border border-purple-500/30">
                <Sparkles size={24} className="text-purple-400" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-white">Interactive Demo</h1>
                <p className="text-sm text-zinc-400">
                  Experience real-time multi-agent failure detection
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {hasSeenTour && <WalkthroughTrigger onClick={() => setShowWalkthrough(true)} />}
              <Button
                variant="secondary"
                size="sm"
                onClick={() => (window.location.href = '/onboarding')}
              >
                <Link size={14} className="mr-1" />
                Connect Your Agent
              </Button>
            </div>
          </div>
        </div>

        {/* Demo mode banner */}
        <div className="mb-6 px-4 py-3 rounded-lg bg-blue-500/5 border border-blue-500/20 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles size={14} className="text-blue-400" />
            <span className="text-sm text-blue-300">
              Demo Mode — Using curated scenarios. No backend connection required.
            </span>
          </div>
        </div>

        {/* Scenario selector */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 mb-6 scenario-selector">
          <DemoScenarioSelector
            scenarios={allDemoScenarios}
            activeScenarioId={activeScenarioId}
            onSelect={handleScenarioChange}
          />
        </div>

        {/* Controls */}
        <div className="flex items-center gap-4 mb-6">
          {demoStep === 0 ? (
            <Button onClick={handleStartDemo} leftIcon={<Play size={16} />} size="lg" className="demo-start-button">
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

          {demoStep > 0 && activeScenario && (
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-zinc-800/50 border border-zinc-700">
              <span className="text-sm text-zinc-400">Scenario:</span>
              <span className="text-sm font-medium text-white">{activeScenario.title}</span>
              {hasDetections && (
                <span className="flex items-center gap-1 text-xs text-red-400">
                  <AlertTriangle size={12} />
                  {activeScenario.detections.length} issues
                </span>
              )}
            </div>
          )}
        </div>

        {/* Running demo view */}
        {demoStep > 0 && activeScenario && (
          <>
            <div className="metrics-panel">
              <AgentMetricsPanel metrics={demo.agentMetrics} />
            </div>

            <div className="mt-6 grid lg:grid-cols-3 gap-6">
              {/* Main content: loop visualization or trace info */}
              <div className="lg:col-span-2">
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-white">Agent State Timeline</h2>
                  {activeScenario.highlights?.explanation && (
                    <p className="text-xs text-zinc-500 max-w-sm text-right">
                      {activeScenario.highlights.explanation}
                    </p>
                  )}
                </div>

                <LoopVisualization
                  states={activeScenario.traces[0]?.states || []}
                />
              </div>

              {/* Sidebar: detection feed */}
              <div className="space-y-6">
                <div className="detection-feed">
                  <LiveDetectionFeed
                    detections={activeScenario.detections}
                    isActive={demo.isSimulating}
                  />
                </div>
              </div>
            </div>
          </>
        )}

        {/* Pre-start view */}
        {demoStep === 0 && activeScenario && (
          <div className="mt-8 grid lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 p-8 rounded-2xl border border-zinc-700 bg-gradient-to-br from-zinc-800/50 to-zinc-900/50 text-center">
              <div className="max-w-md mx-auto">
                <div className="p-4 rounded-full bg-zinc-800 border border-zinc-700 w-16 h-16 mx-auto mb-4 flex items-center justify-center">
                  <Play size={24} className="text-blue-400" />
                </div>
                <h3 className="text-xl font-semibold text-white mb-2">
                  {activeScenario.title}
                </h3>
                <p className="text-zinc-400 mb-6">{activeScenario.description}</p>
                <Button onClick={handleStartDemo} size="lg" leftIcon={<Play size={16} />}>
                  Start Demo
                </Button>
              </div>
            </div>

            <div className="trace-upload">
              <TraceUpload />
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}
