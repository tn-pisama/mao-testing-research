'use client'

import { useState, useEffect } from 'react'
import { 
  TrendingUp, TrendingDown, Minus, Play, RefreshCw,
  ArrowRight, CheckCircle, XCircle, AlertCircle, Clock
} from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { Button } from '@/components/ui/Button'

interface AccuracyMetric {
  type: string
  label: string
  value: number
  trend: 'up' | 'down' | 'stable'
  change: number
  category: 'system' | 'inter-agent' | 'verification'
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

interface Handoff {
  id: string
  from: string
  to: string
  status: 'success' | 'failed' | 'warning'
  latency: number
  dataLoss: boolean
}

const DEMO_ACCURACY: AccuracyMetric[] = [
  { type: 'specification_mismatch', label: 'Spec Mismatch (F1)', value: 94.1, trend: 'up', change: 1.2, category: 'system' },
  { type: 'poor_decomposition', label: 'Decomposition (F2)', value: 91.8, trend: 'stable', change: 0.1, category: 'system' },
  { type: 'state_corruption', label: 'State Corruption (F3/F4)', value: 91.4, trend: 'up', change: 0.8, category: 'system' },
  { type: 'flawed_workflow', label: 'Workflow (F5)', value: 89.2, trend: 'up', change: 2.1, category: 'system' },
  { type: 'task_derailment', label: 'Derailment (F6)', value: 88.5, trend: 'down', change: -0.3, category: 'inter-agent' },
  { type: 'context_neglect', label: 'Context Neglect (F7)', value: 92.3, trend: 'up', change: 1.5, category: 'inter-agent' },
  { type: 'infinite_loop', label: 'Infinite Loop (F8/F9)', value: 96.2, trend: 'up', change: 1.3, category: 'inter-agent' },
  { type: 'communication', label: 'Communication (F10)', value: 87.1, trend: 'down', change: -0.5, category: 'inter-agent' },
  { type: 'persona_drift', label: 'Persona Drift (F11)', value: 85.4, trend: 'stable', change: 0.2, category: 'inter-agent' },
  { type: 'deadlock', label: 'Deadlock (F12-F14)', value: 93.8, trend: 'stable', change: 0.1, category: 'verification' },
]

const DEMO_FIX_EFFECTIVENESS: AccuracyMetric[] = [
  { type: 'max_iterations', label: 'max_iterations', value: 94, trend: 'up', change: 2.1, category: 'system' },
  { type: 'state_validation', label: 'state_validation', value: 87, trend: 'up', change: 1.5, category: 'system' },
  { type: 'timeout', label: 'timeout', value: 92, trend: 'stable', change: 0.0, category: 'system' },
  { type: 'role_reinforcement', label: 'role_reinforcement', value: 81, trend: 'down', change: -1.2, category: 'inter-agent' },
]

const DEMO_INTEGRATIONS: Integration[] = [
  { name: 'LangChain', version: '0.3.x', passed: 24, total: 24 },
  { name: 'CrewAI', version: '0.8.x', passed: 18, total: 18 },
  { name: 'AutoGen', version: '0.4.x', passed: 15, total: 16 },
  { name: 'LangGraph', version: '0.2.x', passed: 12, total: 12 },
]

const DEMO_RUNS: TestRun[] = [
  { id: '1', timestamp: '2024-12-29 14:32', name: 'Golden Dataset', passed: 420, total: 420 },
  { id: '2', timestamp: '2024-12-29 14:30', name: 'LangChain Suite', passed: 24, total: 24 },
  { id: '3', timestamp: '2024-12-29 14:28', name: 'Fix Validation', passed: 31, total: 32 },
]

const DEMO_HANDOFFS: Handoff[] = [
  { id: 'h1', from: 'Planner', to: 'Researcher', status: 'success', latency: 245, dataLoss: false },
  { id: 'h2', from: 'Researcher', to: 'Analyzer', status: 'success', latency: 312, dataLoss: false },
  { id: 'h3', from: 'Analyzer', to: 'Writer', status: 'warning', latency: 1250, dataLoss: false },
  { id: 'h4', from: 'Writer', to: 'Reviewer', status: 'failed', latency: 0, dataLoss: true },
  { id: 'h5', from: 'Reviewer', to: 'Publisher', status: 'success', latency: 189, dataLoss: false },
]

export default function TestingPage() {
  const [isLoading, setIsLoading] = useState(true)
  const [isRunning, setIsRunning] = useState(false)
  const [accuracy, setAccuracy] = useState<AccuracyMetric[]>([])
  const [fixEffectiveness, setFixEffectiveness] = useState<AccuracyMetric[]>([])
  const [integrations, setIntegrations] = useState<Integration[]>([])
  const [recentRuns, setRecentRuns] = useState<TestRun[]>([])
  const [handoffs, setHandoffs] = useState<Handoff[]>([])
  const [activeTab, setActiveTab] = useState<'accuracy' | 'handoffs'>('accuracy')

  useEffect(() => {
    setTimeout(() => {
      setAccuracy(DEMO_ACCURACY)
      setFixEffectiveness(DEMO_FIX_EFFECTIVENESS)
      setIntegrations(DEMO_INTEGRATIONS)
      setRecentRuns(DEMO_RUNS)
      setHandoffs(DEMO_HANDOFFS)
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

  const systemMetrics = accuracy.filter(m => m.category === 'system')
  const interAgentMetrics = accuracy.filter(m => m.category === 'inter-agent')
  const verificationMetrics = accuracy.filter(m => m.category === 'verification')

  return (
    <Layout>
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white">Testing Dashboard</h1>
            <p className="text-slate-400 text-sm mt-1">MAST 14-Mode Detection Accuracy</p>
          </div>
          <Button 
            onClick={runTests} 
            loading={isRunning}
            leftIcon={isRunning ? <RefreshCw className="animate-spin" size={16} /> : <Play size={16} />}
          >
            {isRunning ? 'Running...' : 'Run Tests'}
          </Button>
        </div>

        <div className="flex gap-2 mb-6">
          <button
            onClick={() => setActiveTab('accuracy')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === 'accuracy'
                ? 'bg-primary-600 text-white'
                : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
            }`}
          >
            Detection Accuracy
          </button>
          <button
            onClick={() => setActiveTab('handoffs')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === 'handoffs'
                ? 'bg-primary-600 text-white'
                : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
            }`}
          >
            Handoff Testing
          </button>
        </div>

        {activeTab === 'accuracy' ? (
          <>
            <div className="grid lg:grid-cols-3 gap-6 mb-6">
              <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
                <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  System Design (F1-F5)
                  <span className="text-xs text-slate-400 font-normal">(24hr avg)</span>
                </h2>
                <div className="space-y-3">
                  {systemMetrics.map((metric) => (
                    <div key={metric.type} className="flex items-center justify-between">
                      <span className="text-slate-300 text-sm">{metric.label}</span>
                      <div className="flex items-center gap-2">
                        <span className={`font-mono font-medium ${
                          metric.value >= 90 ? 'text-emerald-400' : 
                          metric.value >= 80 ? 'text-amber-400' : 'text-red-400'
                        }`}>
                          {metric.value.toFixed(1)}%
                        </span>
                        <TrendIcon trend={metric.trend} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
                <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  Inter-Agent (F6-F11)
                  <span className="text-xs text-slate-400 font-normal">(24hr avg)</span>
                </h2>
                <div className="space-y-3">
                  {interAgentMetrics.map((metric) => (
                    <div key={metric.type} className="flex items-center justify-between">
                      <span className="text-slate-300 text-sm">{metric.label}</span>
                      <div className="flex items-center gap-2">
                        <span className={`font-mono font-medium ${
                          metric.value >= 90 ? 'text-emerald-400' : 
                          metric.value >= 80 ? 'text-amber-400' : 'text-red-400'
                        }`}>
                          {metric.value.toFixed(1)}%
                        </span>
                        <TrendIcon trend={metric.trend} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
                <h2 className="text-lg font-semibold text-white mb-4">Verification (F12-F14)</h2>
                <div className="space-y-3">
                  {verificationMetrics.map((metric) => (
                    <div key={metric.type} className="flex items-center justify-between">
                      <span className="text-slate-300 text-sm">{metric.label}</span>
                      <div className="flex items-center gap-2">
                        <span className={`font-mono font-medium ${
                          metric.value >= 90 ? 'text-emerald-400' : 
                          metric.value >= 80 ? 'text-amber-400' : 'text-red-400'
                        }`}>
                          {metric.value.toFixed(1)}%
                        </span>
                        <TrendIcon trend={metric.trend} />
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-6 pt-4 border-t border-slate-700">
                  <h3 className="text-sm font-medium text-white mb-3">Fix Effectiveness</h3>
                  <div className="space-y-2">
                    {fixEffectiveness.slice(0, 3).map((metric) => (
                      <div key={metric.type} className="flex items-center justify-between">
                        <span className="text-slate-400 font-mono text-xs">{metric.label}</span>
                        <div className="flex items-center gap-2">
                          <div className="w-16 bg-slate-700 rounded-full h-1.5">
                            <div 
                              className={`h-1.5 rounded-full ${
                                metric.value >= 90 ? 'bg-emerald-500' : 
                                metric.value >= 80 ? 'bg-amber-500' : 'bg-red-500'
                              }`}
                              style={{ width: `${metric.value}%` }}
                            />
                          </div>
                          <span className="font-mono text-white text-xs w-8 text-right">
                            {metric.value}%
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <div className="grid lg:grid-cols-2 gap-6">
              <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
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
          </>
        ) : (
          <div className="space-y-6">
            <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
              <h2 className="text-lg font-semibold text-white mb-4">Agent Handoff Analysis</h2>
              <div className="space-y-3">
                {handoffs.map((handoff, idx) => (
                  <div 
                    key={handoff.id}
                    className={`flex items-center gap-4 p-4 rounded-lg border ${
                      handoff.status === 'success' ? 'border-slate-600 bg-slate-700/30' :
                      handoff.status === 'warning' ? 'border-amber-500/30 bg-amber-500/5' :
                      'border-red-500/30 bg-red-500/5'
                    }`}
                  >
                    <div className="flex-shrink-0">
                      {handoff.status === 'success' ? (
                        <CheckCircle className="text-emerald-400" size={20} />
                      ) : handoff.status === 'warning' ? (
                        <AlertCircle className="text-amber-400" size={20} />
                      ) : (
                        <XCircle className="text-red-400" size={20} />
                      )}
                    </div>
                    <div className="flex-1 flex items-center gap-3">
                      <span className="bg-slate-700 px-3 py-1 rounded-lg text-white text-sm">
                        {handoff.from}
                      </span>
                      <ArrowRight className="text-slate-500" size={16} />
                      <span className="bg-slate-700 px-3 py-1 rounded-lg text-white text-sm">
                        {handoff.to}
                      </span>
                    </div>
                    <div className="flex items-center gap-6 text-sm">
                      {handoff.latency > 0 && (
                        <span className={`flex items-center gap-1 ${
                          handoff.latency > 1000 ? 'text-amber-400' : 'text-slate-400'
                        }`}>
                          <Clock size={14} />
                          {handoff.latency}ms
                        </span>
                      )}
                      {handoff.dataLoss && (
                        <span className="text-red-400 text-xs px-2 py-0.5 bg-red-400/10 rounded-full">
                          Data Loss
                        </span>
                      )}
                      <span className={`px-2 py-0.5 rounded-full text-xs ${
                        handoff.status === 'success' ? 'bg-emerald-400/10 text-emerald-400' :
                        handoff.status === 'warning' ? 'bg-amber-400/10 text-amber-400' :
                        'bg-red-400/10 text-red-400'
                      }`}>
                        {handoff.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="grid lg:grid-cols-3 gap-6">
              <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
                <h3 className="text-white font-semibold mb-4">Handoff Summary</h3>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Total Handoffs</span>
                    <span className="text-white font-mono">{handoffs.length}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Success Rate</span>
                    <span className="text-emerald-400 font-mono">
                      {Math.round((handoffs.filter(h => h.status === 'success').length / handoffs.length) * 100)}%
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Data Loss Events</span>
                    <span className="text-red-400 font-mono">
                      {handoffs.filter(h => h.dataLoss).length}
                    </span>
                  </div>
                </div>
              </div>

              <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
                <h3 className="text-white font-semibold mb-4">Latency Analysis</h3>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Avg Latency</span>
                    <span className="text-white font-mono">
                      {Math.round(handoffs.filter(h => h.latency > 0).reduce((s, h) => s + h.latency, 0) / handoffs.filter(h => h.latency > 0).length)}ms
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Max Latency</span>
                    <span className="text-amber-400 font-mono">
                      {Math.max(...handoffs.map(h => h.latency))}ms
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">SLA Breaches</span>
                    <span className="text-amber-400 font-mono">
                      {handoffs.filter(h => h.latency > 1000).length}
                    </span>
                  </div>
                </div>
              </div>

              <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
                <h3 className="text-white font-semibold mb-4">Test Assertions</h3>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="text-emerald-400" size={16} />
                    <span className="text-slate-300 text-sm">Context completeness</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <XCircle className="text-red-400" size={16} />
                    <span className="text-slate-300 text-sm">No data loss</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <AlertCircle className="text-amber-400" size={16} />
                    <span className="text-slate-300 text-sm">Handoff SLA (&lt;1s)</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle className="text-emerald-400" size={16} />
                    <span className="text-slate-300 text-sm">No circular handoffs</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}
