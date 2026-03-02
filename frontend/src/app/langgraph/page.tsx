'use client'

export const dynamic = 'force-dynamic'

import { useState } from 'react'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import {
  Network, Plus, Copy, CheckCircle, Loader2, WifiOff, Globe, ChevronDown,
} from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { createApiClient } from '@/lib/api'
import { useLangGraphDeployments, useLangGraphAssistants } from '@/hooks/useApiWithFallback'

export default function LangGraphPage() {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()

  const { deployments, isLoading: deploymentsLoading, isDemoMode } = useLangGraphDeployments()
  const { assistants, isLoading: assistantsLoading } = useLangGraphAssistants()

  const [showDeploymentForm, setShowDeploymentForm] = useState(false)
  const [showAssistantForm, setShowAssistantForm] = useState(false)
  const [isRegistering, setIsRegistering] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copiedUrl, setCopiedUrl] = useState<string | null>(null)

  // Deployment form state
  const [deploymentName, setDeploymentName] = useState('')
  const [apiUrl, setApiUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [deploymentId, setDeploymentId] = useState('')
  const [graphName, setGraphName] = useState('')

  // Assistant form state
  const [selectedDeploymentId, setSelectedDeploymentId] = useState('')
  const [assistantId, setAssistantId] = useState('')
  const [graphId, setGraphId] = useState('')
  const [assistantName, setAssistantName] = useState('')

  const isLoading = deploymentsLoading || assistantsLoading
  const webhookUrl = 'https://api.mao-testing.com/api/v1/langgraph/webhook'

  const registerDeployment = async () => {
    if (!deploymentName.trim() || !apiUrl.trim() || !apiKey.trim()) {
      setError('Name, API URL, and API Key are required')
      return
    }
    setIsRegistering(true)
    setError(null)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      await api.registerLangGraphDeployment({
        name: deploymentName, api_url: apiUrl, api_key: apiKey,
        deployment_id: deploymentId || undefined, graph_name: graphName || undefined,
      })
      setShowDeploymentForm(false)
      setDeploymentName('')
      setApiUrl('')
      setApiKey('')
      setDeploymentId('')
      setGraphName('')
    } catch {
      setError('Failed to register deployment. Please try again.')
    }
    setIsRegistering(false)
  }

  const registerAssistant = async () => {
    if (!selectedDeploymentId || !assistantId.trim() || !graphId.trim()) {
      setError('Deployment, Assistant ID, and Graph ID are required')
      return
    }
    setIsRegistering(true)
    setError(null)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      await api.registerLangGraphAssistant({
        deployment_id: selectedDeploymentId, assistant_id: assistantId,
        graph_id: graphId, name: assistantName || undefined,
      })
      setShowAssistantForm(false)
      setAssistantId('')
      setGraphId('')
      setAssistantName('')
    } catch {
      setError('Failed to register assistant. Please try again.')
    }
    setIsRegistering(false)
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    setCopiedUrl(text)
    setTimeout(() => setCopiedUrl(null), 2000)
  }

  return (
    <Layout>
      <div className="p-6 max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-emerald-600/20 rounded-lg">
                <Network className="w-6 h-6 text-emerald-400" />
              </div>
              <h1 className="text-2xl font-bold text-white">LangGraph Deployments</h1>
              {isDemoMode && (
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-lg bg-amber-500/10 border border-amber-500/30">
                  <WifiOff size={14} className="text-amber-400" />
                  <span className="text-xs font-medium text-amber-200">Demo Mode</span>
                </div>
              )}
            </div>
            <p className="text-slate-400">
              Connect LangGraph deployments for graph run monitoring
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Button
              onClick={() => setShowAssistantForm(true)}
              variant="secondary"
              leftIcon={<Plus size={16} />}
              disabled={deployments.length === 0}
            >
              Register Assistant
            </Button>
            <Button
              onClick={() => setShowDeploymentForm(true)}
              leftIcon={<Plus size={16} />}
            >
              Add Deployment
            </Button>
          </div>
        </div>

        {/* Webhook URL Banner */}
        <div className="mb-6 p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-emerald-200">Webhook URL</p>
              <code className="text-sm text-emerald-300">{webhookUrl}</code>
            </div>
            <button
              onClick={() => copyToClipboard(webhookUrl)}
              className="p-2 text-emerald-300 hover:text-white transition-colors"
            >
              {copiedUrl === webhookUrl ? <CheckCircle size={16} className="text-emerald-400" /> : <Copy size={16} />}
            </button>
          </div>
        </div>

        {/* Register Deployment Modal */}
        {showDeploymentForm && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-slate-800 rounded-xl p-6 border border-slate-700 w-full max-w-md">
              <h2 className="text-lg font-semibold text-white mb-4">Add LangGraph Deployment</h2>
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-slate-300 block mb-2">Deployment Name *</label>
                  <input type="text" value={deploymentName} onChange={(e) => setDeploymentName(e.target.value)}
                    placeholder="e.g., Production LangGraph Cloud" className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-emerald-500 focus:outline-none" />
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-300 block mb-2">API URL *</label>
                  <input type="text" value={apiUrl} onChange={(e) => setApiUrl(e.target.value)}
                    placeholder="https://api.langgraph.cloud/v1" className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-emerald-500 focus:outline-none" />
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-300 block mb-2">API Key *</label>
                  <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)}
                    placeholder="lsv2_xxxxxxxxxx" className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-emerald-500 focus:outline-none" />
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-300 block mb-2">Deployment ID</label>
                  <input type="text" value={deploymentId} onChange={(e) => setDeploymentId(e.target.value)}
                    placeholder="Optional" className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-emerald-500 focus:outline-none" />
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-300 block mb-2">Graph Name</label>
                  <input type="text" value={graphName} onChange={(e) => setGraphName(e.target.value)}
                    placeholder="e.g., research_agent" className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-emerald-500 focus:outline-none" />
                </div>
                {error && <p className="text-red-400 text-sm">{error}</p>}
                <div className="flex gap-3 pt-2">
                  <Button onClick={registerDeployment} disabled={isRegistering} loading={isRegistering} className="flex-1">Register</Button>
                  <Button variant="secondary" onClick={() => { setShowDeploymentForm(false); setError(null) }} disabled={isRegistering}>Cancel</Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Register Assistant Modal */}
        {showAssistantForm && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-slate-800 rounded-xl p-6 border border-slate-700 w-full max-w-md">
              <h2 className="text-lg font-semibold text-white mb-4">Register LangGraph Assistant</h2>
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-slate-300 block mb-2">Deployment *</label>
                  <div className="relative">
                    <select value={selectedDeploymentId} onChange={(e) => setSelectedDeploymentId(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-emerald-500 focus:outline-none appearance-none">
                      <option value="">Select deployment...</option>
                      {deployments.map((dep) => (
                        <option key={dep.id} value={dep.id}>{dep.name}</option>
                      ))}
                    </select>
                    <ChevronDown size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                  </div>
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-300 block mb-2">Assistant ID *</label>
                  <input type="text" value={assistantId} onChange={(e) => setAssistantId(e.target.value)}
                    placeholder="e.g., asst_abc123" className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-emerald-500 focus:outline-none" />
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-300 block mb-2">Graph ID *</label>
                  <input type="text" value={graphId} onChange={(e) => setGraphId(e.target.value)}
                    placeholder="e.g., research_graph" className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-emerald-500 focus:outline-none" />
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-300 block mb-2">Name</label>
                  <input type="text" value={assistantName} onChange={(e) => setAssistantName(e.target.value)}
                    placeholder="e.g., Research Assistant" className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-emerald-500 focus:outline-none" />
                </div>
                {error && <p className="text-red-400 text-sm">{error}</p>}
                <div className="flex gap-3 pt-2">
                  <Button onClick={registerAssistant} disabled={isRegistering} loading={isRegistering} className="flex-1">Register</Button>
                  <Button variant="secondary" onClick={() => { setShowAssistantForm(false); setError(null) }} disabled={isRegistering}>Cancel</Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Deployments & Assistants List */}
        <div className="bg-slate-800 rounded-xl border border-slate-700">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-emerald-400 animate-spin" />
            </div>
          ) : deployments.length === 0 ? (
            <div className="text-center py-12 px-4">
              <Network className="w-12 h-12 text-slate-600 mx-auto mb-4" />
              <p className="text-slate-400 mb-2">No LangGraph deployments connected</p>
              <p className="text-slate-500 text-sm">Add a LangGraph deployment to start monitoring graph runs</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-700">
              {deployments.map((dep) => (
                <div key={dep.id} className="p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-white font-medium">{dep.name}</span>
                        {dep.is_active ? (
                          <Badge variant="success" size="sm">Active</Badge>
                        ) : (
                          <Badge variant="default" size="sm">Inactive</Badge>
                        )}
                        <Badge variant="default" size="sm">{dep.ingestion_mode}</Badge>
                      </div>
                      <div className="flex items-center gap-3 text-slate-500 text-sm">
                        <span className="flex items-center gap-1"><Globe size={12} />{dep.api_url}</span>
                        {dep.graph_name && <span>Graph: {dep.graph_name}</span>}
                      </div>
                    </div>
                  </div>

                  {/* Assistants for this deployment */}
                  {assistants.length > 0 && (
                    <div className="mt-3 ml-4 space-y-2">
                      {assistants.map((asst) => (
                        <div key={asst.id} className="p-3 bg-slate-900 rounded-lg flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="text-slate-300 text-sm">{asst.name || asst.assistant_id}</span>
                            <Badge variant="default" size="sm">{asst.graph_id}</Badge>
                            {asst.monitoring_enabled ? (
                              <Badge variant="success" size="sm">Monitoring</Badge>
                            ) : (
                              <Badge variant="default" size="sm">Paused</Badge>
                            )}
                          </div>
                          <div className="text-xs text-slate-500">
                            <span>{asst.total_runs} runs</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Setup Instructions */}
        <div className="mt-6 p-6 bg-slate-800/50 rounded-xl border border-slate-700">
          <h3 className="text-lg font-semibold text-white mb-4">Setup Instructions</h3>
          <ol className="space-y-3 text-sm text-slate-400">
            <li className="flex gap-3">
              <span className="w-6 h-6 bg-emerald-500/20 text-emerald-400 rounded-full flex items-center justify-center text-xs font-medium flex-shrink-0">1</span>
              <span>Add your LangGraph deployment (Cloud or self-hosted) with its API URL and key</span>
            </li>
            <li className="flex gap-3">
              <span className="w-6 h-6 bg-emerald-500/20 text-emerald-400 rounded-full flex items-center justify-center text-xs font-medium flex-shrink-0">2</span>
              <span>Register the assistants (graph configurations) you want to monitor</span>
            </li>
            <li className="flex gap-3">
              <span className="w-6 h-6 bg-emerald-500/20 text-emerald-400 rounded-full flex items-center justify-center text-xs font-medium flex-shrink-0">3</span>
              <span>Configure your LangGraph deployment to send run callbacks to the webhook URL, or use the Python SDK tracer</span>
            </li>
            <li className="flex gap-3">
              <span className="w-6 h-6 bg-emerald-500/20 text-emerald-400 rounded-full flex items-center justify-center text-xs font-medium flex-shrink-0">4</span>
              <span>Graph run traces will automatically appear with recursion and state corruption detection</span>
            </li>
          </ol>

          <div className="mt-4 p-4 bg-slate-900 rounded-lg">
            <p className="text-sm text-slate-500 mb-2">Alternative: Python SDK integration</p>
            <pre className="text-xs text-slate-400 overflow-x-auto">
{`from mao_testing.integrations import LangGraphTracer

tracer = LangGraphTracer()
app = graph.compile()
# Tracer auto-captures state transitions and sends to Pisama`}
            </pre>
          </div>
        </div>
      </div>
    </Layout>
  )
}
