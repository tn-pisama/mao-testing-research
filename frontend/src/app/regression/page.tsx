'use client'

export const dynamic = 'force-dynamic'

import { useState, useEffect, useCallback } from 'react'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import {
  GitBranch, TrendingDown, TrendingUp, AlertTriangle,
  CheckCircle, Clock, Database, RefreshCw, Plus
} from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { Button } from '@/components/ui/Button'
import { createApiClient, Baseline, DriftAlert, ModelFingerprint } from '@/lib/api'

interface DisplayBaseline {
  id: string
  name: string
  model: string
  promptCount: number
  createdAt: string
  lastTested: string
}

interface DisplayDriftAlert {
  id: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  type: 'semantic' | 'performance' | 'format'
  prompt: string
  similarity: number
  detectedAt: string
}

interface DisplayFingerprint {
  model: string
  version: string
  provider: string
  lastSeen: string
  status: 'stable' | 'updated' | 'deprecated'
}

const DEMO_BASELINES: DisplayBaseline[] = [
  {
    id: 'bl-001',
    name: 'Production Prompts v2.1',
    model: 'gpt-4o-2024-08-06',
    promptCount: 47,
    createdAt: '2024-12-15',
    lastTested: '2024-12-29'
  },
  {
    id: 'bl-002',
    name: 'Customer Service Prompts',
    model: 'claude-3-5-sonnet-20241022',
    promptCount: 23,
    createdAt: '2024-12-10',
    lastTested: '2024-12-28'
  },
]

const DEMO_ALERTS: DisplayDriftAlert[] = [
  {
    id: 'da-001',
    severity: 'high',
    type: 'semantic',
    prompt: 'Summarize the following document...',
    similarity: 0.67,
    detectedAt: '2024-12-29 09:15'
  },
  {
    id: 'da-002',
    severity: 'medium',
    type: 'performance',
    prompt: 'Generate a response to customer complaint...',
    similarity: 0.82,
    detectedAt: '2024-12-29 08:30'
  },
  {
    id: 'da-003',
    severity: 'low',
    type: 'format',
    prompt: 'Extract entities from the text...',
    similarity: 0.91,
    detectedAt: '2024-12-28 16:45'
  },
]

const DEMO_FINGERPRINTS: DisplayFingerprint[] = [
  { model: 'gpt-4o', version: '2024-08-06', provider: 'OpenAI', lastSeen: '2024-12-29', status: 'stable' },
  { model: 'gpt-4o', version: '2024-11-20', provider: 'OpenAI', lastSeen: '2024-12-29', status: 'updated' },
  { model: 'claude-3-5-sonnet', version: '20241022', provider: 'Anthropic', lastSeen: '2024-12-29', status: 'stable' },
  { model: 'gpt-4-turbo', version: '2024-04-09', provider: 'OpenAI', lastSeen: '2024-12-20', status: 'deprecated' },
]

function mapBaseline(b: Baseline): DisplayBaseline {
  return {
    id: b.id,
    name: b.name,
    model: b.model,
    promptCount: b.entry_count,
    createdAt: new Date(b.created_at).toLocaleDateString(),
    lastTested: b.last_tested ? new Date(b.last_tested).toLocaleDateString() : 'Never'
  }
}

function mapDriftAlert(a: DriftAlert): DisplayDriftAlert {
  return {
    id: a.id,
    severity: a.severity as 'critical' | 'high' | 'medium' | 'low',
    type: a.drift_type as 'semantic' | 'performance' | 'format',
    prompt: a.prompt,
    similarity: a.similarity,
    detectedAt: new Date(a.detected_at).toLocaleString()
  }
}

function mapFingerprint(f: ModelFingerprint): DisplayFingerprint {
  return {
    model: f.model,
    version: f.version,
    provider: f.provider,
    lastSeen: new Date(f.last_seen).toLocaleDateString(),
    status: f.status as 'stable' | 'updated' | 'deprecated'
  }
}

export default function RegressionPage() {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const [baselines, setBaselines] = useState<DisplayBaseline[]>([])
  const [alerts, setAlerts] = useState<DisplayDriftAlert[]>([])
  const [fingerprints, setFingerprints] = useState<DisplayFingerprint[]>([])
  const [selectedBaseline, setSelectedBaseline] = useState<string | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [isDemoMode, setIsDemoMode] = useState(false)

  const loadData = useCallback(async () => {
    setIsLoading(true)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)

      const [baselinesData, alertsData, fingerprintsData] = await Promise.all([
        api.getBaselines(20, 0),
        api.getDriftAlerts(undefined, 20),
        api.getModelFingerprints(),
      ])

      setBaselines(baselinesData.map(mapBaseline))
      setAlerts(alertsData.map(mapDriftAlert))
      setFingerprints(fingerprintsData.map(mapFingerprint))
      setIsDemoMode(false)
    } catch (err) {
      console.warn('API unavailable, using demo data:', err)
      setBaselines(DEMO_BASELINES)
      setAlerts(DEMO_ALERTS)
      setFingerprints(DEMO_FINGERPRINTS)
      setIsDemoMode(true)
    }
    setIsLoading(false)
  }, [getToken, tenantId])

  useEffect(() => {
    loadData()
  }, [loadData])

  const runRegressionTest = async () => {
    if (!selectedBaseline) return
    setIsRunning(true)

    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)

      // Run the regression test
      const result = await api.testBaseline(selectedBaseline, [])

      // Refresh alerts after test
      const alertsData = await api.getDriftAlerts(undefined, 20)
      setAlerts(alertsData.map(mapDriftAlert))
      setIsDemoMode(false)
    } catch (err) {
      console.warn('Regression test API unavailable:', err)
      setIsDemoMode(true)
    }

    setIsRunning(false)
  }

  const refreshFingerprints = async () => {
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      await api.refreshFingerprints()

      // Reload fingerprints after refresh
      const fingerprintsData = await api.getModelFingerprints()
      setFingerprints(fingerprintsData.map(mapFingerprint))
    } catch (err) {
      console.warn('Fingerprint refresh failed:', err)
    }
  }

  const severityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'text-red-400 bg-red-400/10'
      case 'high': return 'text-orange-400 bg-orange-400/10'
      case 'medium': return 'text-amber-400 bg-amber-400/10'
      case 'low': return 'text-slate-400 bg-slate-400/10'
      default: return 'text-slate-400 bg-slate-400/10'
    }
  }

  const avgSimilarity = alerts.length > 0
    ? alerts.reduce((acc, a) => acc + a.similarity, 0) / alerts.length
    : 0.942

  return (
    <Layout>
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <GitBranch className="text-cyan-400" />
              Model Regression Testing
              {isDemoMode && (
                <span className="text-xs bg-amber-500/20 text-amber-400 px-2 py-1 rounded-full ml-2">
                  Demo Mode
                </span>
              )}
            </h1>
            <p className="text-slate-400 text-sm mt-1">
              Detect behavioral drift when models are updated
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" leftIcon={<Plus size={16} />}>
              Create Baseline
            </Button>
            <Button
              onClick={runRegressionTest}
              disabled={!selectedBaseline || isRunning}
              loading={isRunning}
              leftIcon={<RefreshCw size={16} />}
            >
              {isRunning ? 'Testing...' : 'Run Regression Test'}
            </Button>
          </div>
        </div>

        <div className="grid lg:grid-cols-4 gap-4 mb-6">
          <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
            <div className="flex items-center gap-2 text-slate-400 text-sm mb-2">
              <Database size={16} />
              Baselines
            </div>
            <span className="text-2xl font-bold text-white">{baselines.length}</span>
          </div>
          <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
            <div className="flex items-center gap-2 text-slate-400 text-sm mb-2">
              <AlertTriangle size={16} />
              Active Alerts
            </div>
            <span className="text-2xl font-bold text-amber-400">{alerts.length}</span>
          </div>
          <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
            <div className="flex items-center gap-2 text-slate-400 text-sm mb-2">
              <TrendingUp size={16} />
              Avg Similarity
            </div>
            <span className="text-2xl font-bold text-emerald-400">
              {(avgSimilarity * 100).toFixed(1)}%
            </span>
          </div>
          <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
            <div className="flex items-center gap-2 text-slate-400 text-sm mb-2">
              <Clock size={16} />
              Models Tracked
            </div>
            <span className="text-2xl font-bold text-white">{fingerprints.length}</span>
          </div>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-cyan-400"></div>
          </div>
        ) : (
          <div className="grid lg:grid-cols-3 gap-6 mb-6">
            <div className="lg:col-span-2">
              <div className="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6">
                <h2 className="text-lg font-semibold text-white mb-4">Baselines</h2>
                <div className="space-y-2">
                  {baselines.map((baseline) => (
                    <button
                      key={baseline.id}
                      onClick={() => setSelectedBaseline(baseline.id)}
                      className={`w-full p-4 rounded-lg border text-left transition-all ${
                        selectedBaseline === baseline.id
                          ? 'border-primary-500 bg-primary-500/10'
                          : 'border-slate-600 bg-slate-700/50 hover:border-slate-500'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="text-white font-medium">{baseline.name}</span>
                          <div className="flex items-center gap-3 mt-1">
                            <span className="text-slate-500 text-sm font-mono">{baseline.model}</span>
                            <span className="text-slate-500 text-sm">{baseline.promptCount} prompts</span>
                          </div>
                        </div>
                        <div className="text-right text-sm">
                          <div className="text-slate-400">Last tested</div>
                          <div className="text-white">{baseline.lastTested}</div>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
                <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <AlertTriangle className="text-amber-400" size={20} />
                  Drift Alerts
                </h2>
                <div className="space-y-2">
                  {alerts.map((alert) => (
                    <div
                      key={alert.id}
                      className="p-4 rounded-lg border border-slate-600 bg-slate-700/30"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex items-start gap-3">
                          <span className={`px-2 py-0.5 rounded-full text-xs ${severityColor(alert.severity)}`}>
                            {alert.severity}
                          </span>
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-white">{alert.type} drift</span>
                              <span className={`text-sm font-mono ${
                                alert.similarity >= 0.9 ? 'text-emerald-400' :
                                alert.similarity >= 0.7 ? 'text-amber-400' : 'text-red-400'
                              }`}>
                                {(alert.similarity * 100).toFixed(0)}% similar
                              </span>
                            </div>
                            <p className="text-slate-400 text-sm mt-1 truncate max-w-md">
                              {alert.prompt}
                            </p>
                          </div>
                        </div>
                        <span className="text-slate-500 text-sm">{alert.detectedAt}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div>
              <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-white">Model Fingerprints</h2>
                  <Button variant="ghost" size="sm" onClick={refreshFingerprints}>
                    <RefreshCw size={14} />
                  </Button>
                </div>
                <div className="space-y-3">
                  {fingerprints.map((fp, idx) => (
                    <div
                      key={idx}
                      className="p-3 rounded-lg bg-slate-700/50 border border-slate-600"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-white font-medium text-sm">{fp.model}</span>
                        <span className={`px-2 py-0.5 rounded-full text-xs ${
                          fp.status === 'stable' ? 'bg-emerald-400/10 text-emerald-400' :
                          fp.status === 'updated' ? 'bg-amber-400/10 text-amber-400' :
                          'bg-red-400/10 text-red-400'
                        }`}>
                          {fp.status}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-400">{fp.provider}</span>
                        <span className="text-slate-500 font-mono">{fp.version}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}
