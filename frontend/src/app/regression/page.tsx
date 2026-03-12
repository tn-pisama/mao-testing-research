'use client'

export const dynamic = 'force-dynamic'

import { useState, useEffect, useCallback } from 'react'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import {
  GitBranch, TrendingUp, AlertTriangle,
  Clock, Database, RefreshCw, Plus
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
  const [error, setError] = useState<string | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [isCreating, setIsCreating] = useState(false)

  const loadData = useCallback(async () => {
    setIsLoading(true)
    setError(null)
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
    } catch (err) {
      console.error('Failed to load regression data:', err)
      setError('Failed to load regression data.')
    }
    setIsLoading(false)
  }, [getToken, tenantId])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- data fetching pattern
    loadData()
  }, [loadData])

  const runRegressionTest = async () => {
    if (!selectedBaseline) return
    setIsRunning(true)

    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)

      // Run the regression test
      const _result = await api.testBaseline(selectedBaseline, [])

      // Refresh alerts after test
      const alertsData = await api.getDriftAlerts(undefined, 20)
      setAlerts(alertsData.map(mapDriftAlert))
    } catch (err) {
      console.error('Regression test failed:', err)
      setError('Failed to run regression test. Please try again.')
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

  const createBaseline = async (name: string, model: string, description: string) => {
    setIsCreating(true)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      await api.createBaseline(name, description, model)
      await loadData()
      setShowCreateModal(false)
    } catch (err) {
      console.error('Failed to create baseline:', err)
      setError('Failed to create baseline. Please try again.')
    }
    setIsCreating(false)
  }

  const severityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'text-red-400 bg-red-400/10'
      case 'high': return 'text-orange-400 bg-orange-400/10'
      case 'medium': return 'text-amber-400 bg-amber-400/10'
      case 'low': return 'text-zinc-400 bg-zinc-400/10'
      default: return 'text-zinc-400 bg-zinc-400/10'
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
              <GitBranch className="text-blue-400" />
              Model Regression Testing
            </h1>
            <p className="text-zinc-400 text-sm mt-1">
              Detect behavioral drift when models are updated
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              leftIcon={<Plus size={16} />}
              onClick={() => setShowCreateModal(true)}
            >
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

        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-lg flex items-center justify-between">
            <div className="flex items-center gap-3">
              <AlertTriangle className="w-5 h-5 text-red-400" />
              <p className="text-red-300">{error}</p>
            </div>
            <Button variant="secondary" size="sm" onClick={loadData}>
              Retry
            </Button>
          </div>
        )}

        <div className="grid lg:grid-cols-4 gap-4 mb-6">
          <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700">
            <div className="flex items-center gap-2 text-zinc-400 text-sm mb-2">
              <Database size={16} />
              Baselines
            </div>
            <span className="text-2xl font-bold text-white">{baselines.length}</span>
          </div>
          <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700">
            <div className="flex items-center gap-2 text-zinc-400 text-sm mb-2">
              <AlertTriangle size={16} />
              Active Alerts
            </div>
            <span className="text-2xl font-bold text-amber-400">{alerts.length}</span>
          </div>
          <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700">
            <div className="flex items-center gap-2 text-zinc-400 text-sm mb-2">
              <TrendingUp size={16} />
              Avg Similarity
            </div>
            <span className="text-2xl font-bold text-emerald-400">
              {(avgSimilarity * 100).toFixed(1)}%
            </span>
          </div>
          <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700">
            <div className="flex items-center gap-2 text-zinc-400 text-sm mb-2">
              <Clock size={16} />
              Models Tracked
            </div>
            <span className="text-2xl font-bold text-white">{fingerprints.length}</span>
          </div>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400"></div>
          </div>
        ) : (
          <div className="grid lg:grid-cols-3 gap-6 mb-6">
            <div className="lg:col-span-2">
              <div className="bg-zinc-800 rounded-xl p-6 border border-zinc-700 mb-6">
                <h2 className="text-lg font-semibold text-white mb-4">Baselines</h2>
                <div className="space-y-2">
                  {baselines.map((baseline) => (
                    <button
                      key={baseline.id}
                      onClick={() => setSelectedBaseline(baseline.id)}
                      className={`w-full p-4 rounded-lg border text-left transition-all ${
                        selectedBaseline === baseline.id
                          ? 'border-blue-500 bg-blue-500/10'
                          : 'border-zinc-600 bg-zinc-700/50 hover:border-zinc-500'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="text-white font-medium">{baseline.name}</span>
                          <div className="flex items-center gap-3 mt-1">
                            <span className="text-zinc-500 text-sm">{baseline.model}</span>
                            <span className="text-zinc-500 text-sm">{baseline.promptCount} prompts</span>
                          </div>
                        </div>
                        <div className="text-right text-sm">
                          <div className="text-zinc-400">Last tested</div>
                          <div className="text-white">{baseline.lastTested}</div>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              <div className="bg-zinc-800 rounded-xl p-6 border border-zinc-700">
                <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <AlertTriangle className="text-amber-400" size={20} />
                  Drift Alerts
                </h2>
                <div className="space-y-2">
                  {alerts.map((alert) => (
                    <div
                      key={alert.id}
                      className="p-4 rounded-lg border border-zinc-600 bg-zinc-700/30"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex items-start gap-3">
                          <span className={`px-2 py-0.5 rounded-full text-xs ${severityColor(alert.severity)}`}>
                            {alert.severity}
                          </span>
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-white">{alert.type} drift</span>
                              <span className={`text-sm ${
                                alert.similarity >= 0.9 ? 'text-emerald-400' :
                                alert.similarity >= 0.7 ? 'text-amber-400' : 'text-red-400'
                              }`}>
                                {(alert.similarity * 100).toFixed(0)}% similar
                              </span>
                            </div>
                            <p className="text-zinc-400 text-sm mt-1 truncate max-w-md">
                              {alert.prompt}
                            </p>
                          </div>
                        </div>
                        <span className="text-zinc-500 text-sm">{alert.detectedAt}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div>
              <div className="bg-zinc-800 rounded-xl p-6 border border-zinc-700">
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
                      className="p-3 rounded-lg bg-zinc-700/50 border border-zinc-600"
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
                        <span className="text-zinc-400">{fp.provider}</span>
                        <span className="text-zinc-500">{fp.version}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Create Baseline Modal */}
        {showCreateModal && (
          <CreateBaselineModal
            isCreating={isCreating}
            onClose={() => setShowCreateModal(false)}
            onCreate={createBaseline}
          />
        )}
      </div>
    </Layout>
  )
}

interface CreateBaselineModalProps {
  isCreating: boolean
  onClose: () => void
  onCreate: (name: string, model: string, description: string) => void
}

function CreateBaselineModal({ isCreating, onClose, onCreate }: CreateBaselineModalProps) {
  const [name, setName] = useState('')
  const [model, setModel] = useState('')
  const [description, setDescription] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (name && model) {
      onCreate(name, model, description)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-zinc-800 rounded-xl p-6 border border-zinc-700 w-full max-w-md">
        <h2 className="text-lg font-semibold text-white mb-4">Create Baseline</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-sm font-medium text-zinc-300 block mb-2">
              Baseline Name *
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Production Prompts v3.0"
              className="w-full bg-zinc-900 border border-zinc-600 rounded-lg p-3 text-white text-sm focus:border-blue-500 focus:outline-none"
              required
            />
          </div>

          <div>
            <label className="text-sm font-medium text-zinc-300 block mb-2">
              Model *
            </label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-600 rounded-lg p-3 text-white text-sm focus:border-blue-500 focus:outline-none"
              required
            >
              <option value="">Select a model...</option>
              <option value="gpt-4o">GPT-4o</option>
              <option value="gpt-4o-mini">GPT-4o Mini</option>
              <option value="gpt-4-turbo">GPT-4 Turbo</option>
              <option value="claude-3-5-sonnet">Claude 3.5 Sonnet</option>
              <option value="claude-3-opus">Claude 3 Opus</option>
              <option value="gemini-pro">Gemini Pro</option>
              <option value="other">Other</option>
            </select>
          </div>

          <div>
            <label className="text-sm font-medium text-zinc-300 block mb-2">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe the purpose of this baseline..."
              rows={3}
              className="w-full bg-zinc-900 border border-zinc-600 rounded-lg p-3 text-white text-sm focus:border-blue-500 focus:outline-none resize-none"
            />
          </div>

          <div className="flex gap-3 pt-2">
            <Button
              type="submit"
              disabled={!name || !model || isCreating}
              loading={isCreating}
              className="flex-1"
            >
              Create Baseline
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={onClose}
              disabled={isCreating}
            >
              Cancel
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
