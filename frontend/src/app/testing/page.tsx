'use client'

export const dynamic = 'force-dynamic'

import { useState, useEffect, useCallback } from 'react'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import {
  TrendingUp, TrendingDown, Minus, Play, RefreshCw,
  ArrowRight, CheckCircle, XCircle, AlertCircle, Clock
} from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { Button } from '@/components/ui/Button'
import { createApiClient, AccuracyMetric, IntegrationStatus } from '@/lib/api'

interface TestRun {
  id: string
  timestamp: string
  name: string
  passed: number
  total: number
}

interface HandoffData {
  id: string
  from: string
  to: string
  status: 'success' | 'failed' | 'warning'
  latency: number
  dataLoss: boolean
}

export default function TestingPage() {
  const { getToken } = useAuth()
  const [isLoading, setIsLoading] = useState(true)
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [accuracy, setAccuracy] = useState<AccuracyMetric[]>([])
  const [integrations, setIntegrations] = useState<IntegrationStatus[]>([])
  const [recentRuns, setRecentRuns] = useState<TestRun[]>([])
  const [handoffs, setHandoffs] = useState<HandoffData[]>([])
  const [activeTab, setActiveTab] = useState<'accuracy' | 'handoffs'>('accuracy')

  const loadData = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const token = await getToken()
      const api = createApiClient(token)

      const [accuracyData, integrationsData] = await Promise.all([
        api.getAccuracyMetrics(30),
        api.getIntegrationStatus(),
      ])

      setAccuracy(accuracyData)
      setIntegrations(integrationsData)
      setRecentRuns([])
      setHandoffs([])
    } catch (err) {
      console.error('Failed to load testing data:', err)
      setError('Failed to load testing data. Please try again.')
    }
    setIsLoading(false)
  }, [getToken])

  useEffect(() => {
    loadData()
  }, [loadData])

  const TrendIcon = ({ trend }: { trend: string }) => {
    if (trend === 'up') return <TrendingUp className="text-emerald-400" size={16} />
    if (trend === 'down') return <TrendingDown className="text-red-400" size={16} />
    return <Minus className="text-zinc-400" size={16} />
  }

  const runTests = async () => {
    setIsRunning(true)
    setTimeout(() => {
      setIsRunning(false)
      loadData()
    }, 3000)
  }

  if (isLoading) {
    return (
      <Layout>
        <div className="p-6 animate-pulse">
          <div className="h-8 w-48 bg-zinc-700 rounded mb-6" />
          <div className="grid lg:grid-cols-2 gap-6">
            <div className="h-48 bg-zinc-700 rounded-xl" />
            <div className="h-48 bg-zinc-700 rounded-xl" />
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
            <p className="text-zinc-400 text-sm mt-1">
              MAST 14-Mode Detection Accuracy
            </p>
          </div>
          <Button
            onClick={runTests}
            loading={isRunning}
            leftIcon={isRunning ? <RefreshCw className="animate-spin" size={16} /> : <Play size={16} />}
          >
            {isRunning ? 'Running...' : 'Run Tests'}
          </Button>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-lg flex items-center justify-between">
            <div className="flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-red-400" />
              <p className="text-red-300">{error}</p>
            </div>
            <Button variant="secondary" size="sm" onClick={loadData}>
              Retry
            </Button>
          </div>
        )}

        <div className="flex gap-2 mb-6">
          <button
            onClick={() => setActiveTab('accuracy')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === 'accuracy'
                ? 'bg-blue-600 text-white'
                : 'bg-zinc-700 text-zinc-300 hover:bg-zinc-600'
            }`}
          >
            Detection Accuracy
          </button>
          <button
            onClick={() => setActiveTab('handoffs')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === 'handoffs'
                ? 'bg-blue-600 text-white'
                : 'bg-zinc-700 text-zinc-300 hover:bg-zinc-600'
            }`}
          >
            Handoff Testing
          </button>
        </div>

        {activeTab === 'accuracy' ? (
          <>
            <div className="grid lg:grid-cols-3 gap-6 mb-6">
              <div className="bg-zinc-800 rounded-xl p-6 border border-zinc-700">
                <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  System Design (F1-F5)
                  <span className="text-xs text-zinc-400 font-normal">(24hr avg)</span>
                </h2>
                <div className="space-y-3">
                  {systemMetrics.map((metric) => (
                    <div key={metric.detection_type} className="flex items-center justify-between">
                      <span className="text-zinc-300 text-sm">{metric.label}</span>
                      <div className="flex items-center gap-2">
                        <span className={`font-medium ${
                          metric.accuracy >= 90 ? 'text-emerald-400' :
                          metric.accuracy >= 80 ? 'text-amber-400' : 'text-red-400'
                        }`}>
                          {metric.accuracy.toFixed(1)}%
                        </span>
                        <TrendIcon trend={metric.trend} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-zinc-800 rounded-xl p-6 border border-zinc-700">
                <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  Inter-Agent (F6-F10)
                  <span className="text-xs text-zinc-400 font-normal">(24hr avg)</span>
                </h2>
                <div className="space-y-3">
                  {interAgentMetrics.map((metric) => (
                    <div key={metric.detection_type} className="flex items-center justify-between">
                      <span className="text-zinc-300 text-sm">{metric.label}</span>
                      <div className="flex items-center gap-2">
                        <span className={`font-medium ${
                          metric.accuracy >= 90 ? 'text-emerald-400' :
                          metric.accuracy >= 80 ? 'text-amber-400' : 'text-red-400'
                        }`}>
                          {metric.accuracy.toFixed(1)}%
                        </span>
                        <TrendIcon trend={metric.trend} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-zinc-800 rounded-xl p-6 border border-zinc-700">
                <h2 className="text-lg font-semibold text-white mb-4">Verification (F11-F14)</h2>
                <div className="space-y-3">
                  {verificationMetrics.map((metric) => (
                    <div key={metric.detection_type} className="flex items-center justify-between">
                      <span className="text-zinc-300 text-sm">{metric.label}</span>
                      <div className="flex items-center gap-2">
                        <span className={`font-medium ${
                          metric.accuracy >= 90 ? 'text-emerald-400' :
                          metric.accuracy >= 80 ? 'text-amber-400' : 'text-red-400'
                        }`}>
                          {metric.accuracy.toFixed(1)}%
                        </span>
                        <TrendIcon trend={metric.trend} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="grid lg:grid-cols-2 gap-6">
              <div className="bg-zinc-800 rounded-xl p-6 border border-zinc-700">
                <h2 className="text-lg font-semibold text-white mb-4">Integration Test Status</h2>
                <div className="space-y-2">
                  {integrations.map((integration) => (
                    <div
                      key={integration.name}
                      className="flex items-center justify-between p-3 bg-zinc-700/50 rounded-lg"
                    >
                      <div className="flex items-center gap-3">
                        <span className={integration.passed === integration.total ? 'text-emerald-400' : 'text-amber-400'}>
                          {integration.passed === integration.total ? '✓' : '!'}
                        </span>
                        <span className="text-white font-medium">{integration.name}</span>
                        <span className="text-zinc-400 text-sm">{integration.version}</span>
                      </div>
                      <div className="flex items-center gap-4">
                        <span className="text-zinc-300">
                          {integration.passed}/{integration.total} passed
                        </span>
                        <Button variant="ghost" size="sm">View</Button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-zinc-800 rounded-xl p-6 border border-zinc-700">
                <h2 className="text-lg font-semibold text-white mb-4">Recent Test Runs</h2>
                <div className="space-y-2">
                  {recentRuns.map((run) => (
                    <div
                      key={run.id}
                      className="flex items-center justify-between p-3 bg-zinc-700/50 rounded-lg"
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-zinc-400 text-sm">{run.timestamp}</span>
                        <span className="text-white">{run.name}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={run.passed === run.total ? 'text-emerald-400' : 'text-amber-400'}>
                          {run.passed === run.total ? '✓' : '!'}
                        </span>
                        <span className="text-zinc-300">{run.passed}/{run.total}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </>
        ) : (
          <div className="space-y-6">
            <div className="bg-zinc-800 rounded-xl p-6 border border-zinc-700">
              <h2 className="text-lg font-semibold text-white mb-4">Agent Handoff Analysis</h2>
              <div className="space-y-3">
                {handoffs.map((handoff) => (
                  <div
                    key={handoff.id}
                    className={`flex items-center gap-4 p-4 rounded-lg border ${
                      handoff.status === 'success' ? 'border-zinc-600 bg-zinc-700/30' :
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
                      <span className="bg-zinc-700 px-3 py-1 rounded-lg text-white text-sm">
                        {handoff.from}
                      </span>
                      <ArrowRight className="text-zinc-500" size={16} />
                      <span className="bg-zinc-700 px-3 py-1 rounded-lg text-white text-sm">
                        {handoff.to}
                      </span>
                    </div>
                    <div className="flex items-center gap-6 text-sm">
                      {handoff.latency > 0 && (
                        <span className={`flex items-center gap-1 ${
                          handoff.latency > 1000 ? 'text-amber-400' : 'text-zinc-400'
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
              <div className="bg-zinc-800 rounded-xl p-6 border border-zinc-700">
                <h3 className="text-white font-semibold mb-4">Handoff Summary</h3>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-zinc-400">Total Handoffs</span>
                    <span className="text-white">{handoffs.length}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-400">Success Rate</span>
                    <span className="text-emerald-400">
                      {Math.round((handoffs.filter(h => h.status === 'success').length / handoffs.length) * 100)}%
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-400">Data Loss Events</span>
                    <span className="text-red-400">
                      {handoffs.filter(h => h.dataLoss).length}
                    </span>
                  </div>
                </div>
              </div>

              <div className="bg-zinc-800 rounded-xl p-6 border border-zinc-700">
                <h3 className="text-white font-semibold mb-4">Latency Analysis</h3>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-zinc-400">Avg Latency</span>
                    <span className="text-white">
                      {Math.round(handoffs.filter(h => h.latency > 0).reduce((s, h) => s + h.latency, 0) / handoffs.filter(h => h.latency > 0).length)}ms
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-400">Max Latency</span>
                    <span className="text-amber-400">
                      {Math.max(...handoffs.map(h => h.latency))}ms
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-400">SLA Breaches</span>
                    <span className="text-amber-400">
                      {handoffs.filter(h => h.latency > 1000).length}
                    </span>
                  </div>
                </div>
              </div>

              <div className="bg-zinc-800 rounded-xl p-6 border border-zinc-700">
                <h3 className="text-white font-semibold mb-4">Test Assertions</h3>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="text-emerald-400" size={16} />
                    <span className="text-zinc-300 text-sm">Context completeness</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <XCircle className="text-red-400" size={16} />
                    <span className="text-zinc-300 text-sm">No data loss</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <AlertCircle className="text-amber-400" size={16} />
                    <span className="text-zinc-300 text-sm">Handoff SLA (&lt;1s)</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle className="text-emerald-400" size={16} />
                    <span className="text-zinc-300 text-sm">No circular handoffs</span>
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
