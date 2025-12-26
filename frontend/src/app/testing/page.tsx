'use client'

import { useState, useEffect } from 'react'
import { TrendingUp, TrendingDown, Minus, Play, RefreshCw } from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { Button } from '@/components/ui/Button'

interface AccuracyMetric {
  type: string
  value: number
  trend: 'up' | 'down' | 'stable'
  change: number
}

interface Integration {
  name: string
  version: string
  passed: number
  total: number
}

interface TestRun {
  id: string
  timestamp: string
  name: string
  passed: number
  total: number
}

const DEMO_ACCURACY: AccuracyMetric[] = [
  { type: 'loop', value: 96.2, trend: 'up', change: 1.3 },
  { type: 'corruption', value: 91.4, trend: 'up', change: 0.8 },
  { type: 'drift', value: 87.1, trend: 'down', change: -0.5 },
  { type: 'deadlock', value: 93.8, trend: 'stable', change: 0.1 },
]

const DEMO_FIX_EFFECTIVENESS: AccuracyMetric[] = [
  { type: 'max_iterations', value: 94, trend: 'up', change: 2.1 },
  { type: 'state_validation', value: 87, trend: 'up', change: 1.5 },
  { type: 'timeout', value: 92, trend: 'stable', change: 0.0 },
  { type: 'role_reinforcement', value: 81, trend: 'down', change: -1.2 },
]

const DEMO_INTEGRATIONS: Integration[] = [
  { name: 'LangChain', version: '0.3.x', passed: 24, total: 24 },
  { name: 'CrewAI', version: '0.8.x', passed: 18, total: 18 },
  { name: 'AutoGen', version: '0.4.x', passed: 15, total: 16 },
  { name: 'LangGraph', version: '0.2.x', passed: 12, total: 12 },
]

const DEMO_RUNS: TestRun[] = [
  { id: '1', timestamp: '2024-12-26 14:32', name: 'Golden Dataset', passed: 420, total: 420 },
  { id: '2', timestamp: '2024-12-26 14:30', name: 'LangChain Suite', passed: 24, total: 24 },
  { id: '3', timestamp: '2024-12-26 14:28', name: 'Fix Validation', passed: 31, total: 32 },
]

export default function TestingPage() {
  const [isLoading, setIsLoading] = useState(true)
  const [isRunning, setIsRunning] = useState(false)
  const [accuracy, setAccuracy] = useState<AccuracyMetric[]>([])
  const [fixEffectiveness, setFixEffectiveness] = useState<AccuracyMetric[]>([])
  const [integrations, setIntegrations] = useState<Integration[]>([])
  const [recentRuns, setRecentRuns] = useState<TestRun[]>([])

  useEffect(() => {
    setTimeout(() => {
      setAccuracy(DEMO_ACCURACY)
      setFixEffectiveness(DEMO_FIX_EFFECTIVENESS)
      setIntegrations(DEMO_INTEGRATIONS)
      setRecentRuns(DEMO_RUNS)
      setIsLoading(false)
    }, 500)
  }, [])

  const TrendIcon = ({ trend }: { trend: string }) => {
    if (trend === 'up') return <TrendingUp className="text-emerald-400" size={16} />
    if (trend === 'down') return <TrendingDown className="text-red-400" size={16} />
    return <Minus className="text-slate-400" size={16} />
  }

  const runTests = async () => {
    setIsRunning(true)
    setTimeout(() => setIsRunning(false), 3000)
  }

  if (isLoading) {
    return (
      <Layout>
        <div className="p-6 animate-pulse">
          <div className="h-8 w-48 bg-slate-700 rounded mb-6" />
          <div className="grid lg:grid-cols-2 gap-6">
            <div className="h-48 bg-slate-700 rounded-xl" />
            <div className="h-48 bg-slate-700 rounded-xl" />
          </div>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white">Testing Dashboard</h1>
            <p className="text-slate-400 text-sm mt-1">Last updated: 2 minutes ago</p>
          </div>
          <Button 
            onClick={runTests} 
            loading={isRunning}
            leftIcon={isRunning ? <RefreshCw className="animate-spin" size={16} /> : <Play size={16} />}
          >
            {isRunning ? 'Running...' : 'Run Tests'}
          </Button>
        </div>

        <div className="grid lg:grid-cols-2 gap-6 mb-6">
          <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              Detection Accuracy
              <span className="text-xs text-slate-400 font-normal">(24hr avg)</span>
            </h2>
            <div className="space-y-3">
              {accuracy.map((metric) => (
                <div key={metric.type} className="flex items-center justify-between">
                  <span className="text-slate-300 capitalize">{metric.type}</span>
                  <div className="flex items-center gap-2">
                    <span className={`font-mono font-medium ${
                      metric.value >= 90 ? 'text-emerald-400' : 
                      metric.value >= 80 ? 'text-amber-400' : 'text-red-400'
                    }`}>
                      {metric.value.toFixed(1)}%
                    </span>
                    <TrendIcon trend={metric.trend} />
                    <span className="text-xs text-slate-500">
                      {metric.change > 0 ? '+' : ''}{metric.change.toFixed(1)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
            <h2 className="text-lg font-semibold text-white mb-4">Fix Effectiveness</h2>
            <div className="space-y-3">
              {fixEffectiveness.map((metric) => (
                <div key={metric.type} className="flex items-center justify-between">
                  <span className="text-slate-300 font-mono text-sm">{metric.type}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-24 bg-slate-700 rounded-full h-2">
                      <div 
                        className={`h-2 rounded-full ${
                          metric.value >= 90 ? 'bg-emerald-500' : 
                          metric.value >= 80 ? 'bg-amber-500' : 'bg-red-500'
                        }`}
                        style={{ width: `${metric.value}%` }}
                      />
                    </div>
                    <span className="font-mono text-white w-12 text-right">
                      {metric.value}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6">
          <h2 className="text-lg font-semibold text-white mb-4">Integration Test Status</h2>
          <div className="space-y-2">
            {integrations.map((integration) => (
              <div 
                key={integration.name}
                className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <span className={integration.passed === integration.total ? 'text-emerald-400' : 'text-amber-400'}>
                    {integration.passed === integration.total ? '✓' : '!'}
                  </span>
                  <span className="text-white font-medium">{integration.name}</span>
                  <span className="text-slate-400 text-sm">{integration.version}</span>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-slate-300">
                    {integration.passed}/{integration.total} passed
                  </span>
                  <Button variant="ghost" size="sm">View</Button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
          <h2 className="text-lg font-semibold text-white mb-4">Recent Test Runs</h2>
          <div className="space-y-2">
            {recentRuns.map((run) => (
              <div 
                key={run.id}
                className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <span className="text-slate-400 text-sm font-mono">{run.timestamp}</span>
                  <span className="text-white">{run.name}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={run.passed === run.total ? 'text-emerald-400' : 'text-amber-400'}>
                    {run.passed === run.total ? '✓' : '!'}
                  </span>
                  <span className="text-slate-300">{run.passed}/{run.total}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Layout>
  )
}
