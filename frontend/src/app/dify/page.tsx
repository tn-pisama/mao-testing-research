'use client'

export const dynamic = 'force-dynamic'

import { useState } from 'react'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import {
  Workflow, Plus, Copy, CheckCircle, Loader2, WifiOff, Globe, ChevronDown,
} from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { createApiClient } from '@/lib/api'
import { useDifyInstances, useDifyApps } from '@/hooks/useApiWithFallback'

export default function DifyPage() {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()

  const { instances, isLoading: instancesLoading, isDemoMode } = useDifyInstances()
  const { apps, isLoading: appsLoading } = useDifyApps()

  const [showInstanceForm, setShowInstanceForm] = useState(false)
  const [showAppForm, setShowAppForm] = useState(false)
  const [isRegistering, setIsRegistering] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copiedUrl, setCopiedUrl] = useState<string | null>(null)

  // Instance form state
  const [instanceName, setInstanceName] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [apiKey, setApiKey] = useState('')

  // App form state
  const [selectedInstanceId, setSelectedInstanceId] = useState('')
  const [appId, setAppId] = useState('')
  const [appName, setAppName] = useState('')
  const [appType, setAppType] = useState('workflow')

  const isLoading = instancesLoading || appsLoading
  const webhookUrl = 'https://api.mao-testing.com/api/v1/dify/webhook'

  const registerInstance = async () => {
    if (!instanceName.trim() || !baseUrl.trim() || !apiKey.trim()) {
      setError('Name, Base URL, and API Key are required')
      return
    }
    setIsRegistering(true)
    setError(null)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      await api.registerDifyInstance({ name: instanceName, base_url: baseUrl, api_key: apiKey })
      setShowInstanceForm(false)
      setInstanceName('')
      setBaseUrl('')
      setApiKey('')
    } catch {
      setError('Failed to register instance. Please try again.')
    }
    setIsRegistering(false)
  }

  const registerApp = async () => {
    if (!selectedInstanceId || !appId.trim()) {
      setError('Instance and App ID are required')
      return
    }
    setIsRegistering(true)
    setError(null)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      await api.registerDifyApp({ instance_id: selectedInstanceId, app_id: appId, app_name: appName || undefined, app_type: appType })
      setShowAppForm(false)
      setAppId('')
      setAppName('')
      setAppType('workflow')
    } catch {
      setError('Failed to register app. Please try again.')
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
              <div className="p-2 bg-violet-600/20 rounded-lg">
                <Workflow className="w-6 h-6 text-violet-400" />
              </div>
              <h1 className="text-2xl font-bold text-white">Dify Apps</h1>
              {isDemoMode && (
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-lg bg-amber-500/10 border border-amber-500/30">
                  <WifiOff size={14} className="text-amber-400" />
                  <span className="text-xs font-medium text-amber-200">Demo Mode</span>
                </div>
              )}
            </div>
            <p className="text-slate-400">
              Connect Dify instances for automated trace ingestion
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Button
              onClick={() => setShowAppForm(true)}
              variant="secondary"
              leftIcon={<Plus size={16} />}
              disabled={instances.length === 0}
            >
              Register App
            </Button>
            <Button
              onClick={() => setShowInstanceForm(true)}
              leftIcon={<Plus size={16} />}
            >
              Add Instance
            </Button>
          </div>
        </div>

        {/* Webhook URL Banner */}
        <div className="mb-6 p-4 bg-violet-500/10 border border-violet-500/30 rounded-xl">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-violet-200">Webhook URL</p>
              <code className="text-sm text-violet-300">{webhookUrl}</code>
            </div>
            <button
              onClick={() => copyToClipboard(webhookUrl)}
              className="p-2 text-violet-300 hover:text-white transition-colors"
              aria-label="Copy webhook URL"
            >
              {copiedUrl === webhookUrl ? <CheckCircle size={16} className="text-emerald-400" /> : <Copy size={16} />}
            </button>
          </div>
        </div>

        {/* Register Instance Modal */}
        {showInstanceForm && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-slate-800 rounded-xl p-6 border border-slate-700 w-full max-w-md">
              <h2 className="text-lg font-semibold text-white mb-4">Add Dify Instance</h2>
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-slate-300 block mb-2">Instance Name *</label>
                  <input type="text" value={instanceName} onChange={(e) => setInstanceName(e.target.value)}
                    placeholder="e.g., Production Dify" className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-violet-500 focus:outline-none" />
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-300 block mb-2">Base URL *</label>
                  <input type="text" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)}
                    placeholder="https://api.dify.ai/v1" className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-violet-500 focus:outline-none" />
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-300 block mb-2">API Key *</label>
                  <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)}
                    placeholder="app-xxxxxxxxxx" className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-violet-500 focus:outline-none" />
                </div>
                {error && <p className="text-red-400 text-sm">{error}</p>}
                <div className="flex gap-3 pt-2">
                  <Button onClick={registerInstance} disabled={isRegistering} loading={isRegistering} className="flex-1">Register</Button>
                  <Button variant="secondary" onClick={() => { setShowInstanceForm(false); setError(null) }} disabled={isRegistering}>Cancel</Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Register App Modal */}
        {showAppForm && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-slate-800 rounded-xl p-6 border border-slate-700 w-full max-w-md">
              <h2 className="text-lg font-semibold text-white mb-4">Register Dify App</h2>
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-slate-300 block mb-2">Instance *</label>
                  <div className="relative">
                    <select value={selectedInstanceId} onChange={(e) => setSelectedInstanceId(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-violet-500 focus:outline-none appearance-none">
                      <option value="">Select instance...</option>
                      {instances.map((inst) => (
                        <option key={inst.id} value={inst.id}>{inst.name}</option>
                      ))}
                    </select>
                    <ChevronDown size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                  </div>
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-300 block mb-2">App ID *</label>
                  <input type="text" value={appId} onChange={(e) => setAppId(e.target.value)}
                    placeholder="e.g., app-abc123" className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-violet-500 focus:outline-none" />
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-300 block mb-2">App Name</label>
                  <input type="text" value={appName} onChange={(e) => setAppName(e.target.value)}
                    placeholder="e.g., Customer Support Bot" className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-violet-500 focus:outline-none" />
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-300 block mb-2">App Type</label>
                  <div className="relative">
                    <select value={appType} onChange={(e) => setAppType(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-violet-500 focus:outline-none appearance-none">
                      <option value="workflow">Workflow</option>
                      <option value="chatbot">Chatbot</option>
                      <option value="agent">Agent</option>
                      <option value="chatflow">Chatflow</option>
                    </select>
                    <ChevronDown size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                  </div>
                </div>
                {error && <p className="text-red-400 text-sm">{error}</p>}
                <div className="flex gap-3 pt-2">
                  <Button onClick={registerApp} disabled={isRegistering} loading={isRegistering} className="flex-1">Register</Button>
                  <Button variant="secondary" onClick={() => { setShowAppForm(false); setError(null) }} disabled={isRegistering}>Cancel</Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Instances & Apps List */}
        <div className="bg-slate-800 rounded-xl border border-slate-700">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-violet-400 animate-spin" />
            </div>
          ) : instances.length === 0 ? (
            <div className="text-center py-12 px-4">
              <Workflow className="w-12 h-12 text-slate-600 mx-auto mb-4" />
              <p className="text-slate-400 mb-2">No Dify instances connected</p>
              <p className="text-slate-400 text-sm">Add a Dify instance to start monitoring workflow runs</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-700">
              {instances.map((inst) => {
                const instanceApps = apps.filter((a) => true) // In demo mode, show all apps
                return (
                  <div key={inst.id} className="p-4">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-white font-medium">{inst.name}</span>
                          {inst.is_active ? (
                            <Badge variant="success" size="sm">Active</Badge>
                          ) : (
                            <Badge variant="default" size="sm">Inactive</Badge>
                          )}
                          <Badge variant="default" size="sm">{inst.ingestion_mode}</Badge>
                        </div>
                        <div className="flex items-center gap-1 text-slate-400 text-sm">
                          <Globe size={12} />
                          <span>{inst.base_url}</span>
                        </div>
                      </div>
                    </div>

                    {/* Apps for this instance */}
                    {instanceApps.length > 0 && (
                      <div className="mt-3 ml-4 space-y-2">
                        {instanceApps.map((app) => (
                          <div key={app.id} className="p-3 bg-slate-900 rounded-lg flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-slate-300 text-sm">{app.app_name || app.app_id}</span>
                              <Badge variant="info" size="sm">{app.app_type}</Badge>
                              {app.monitoring_enabled ? (
                                <Badge variant="success" size="sm">Monitoring</Badge>
                              ) : (
                                <Badge variant="default" size="sm">Paused</Badge>
                              )}
                            </div>
                            <div className="text-xs text-slate-400 flex items-center gap-4">
                              <span>{app.total_runs} runs</span>
                              <span>{app.total_tokens.toLocaleString()} tokens</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Setup Instructions */}
        <div className="mt-6 p-6 bg-slate-800/50 rounded-xl border border-slate-700">
          <h3 className="text-lg font-semibold text-white mb-4">Setup Instructions</h3>
          <ol className="space-y-3 text-sm text-slate-400">
            <li className="flex gap-3">
              <span className="w-6 h-6 bg-violet-500/20 text-violet-400 rounded-full flex items-center justify-center text-xs font-medium flex-shrink-0">1</span>
              <span>Add your Dify instance above with its API URL and key</span>
            </li>
            <li className="flex gap-3">
              <span className="w-6 h-6 bg-violet-500/20 text-violet-400 rounded-full flex items-center justify-center text-xs font-medium flex-shrink-0">2</span>
              <span>Register the apps you want to monitor within the instance</span>
            </li>
            <li className="flex gap-3">
              <span className="w-6 h-6 bg-violet-500/20 text-violet-400 rounded-full flex items-center justify-center text-xs font-medium flex-shrink-0">3</span>
              <span>In Dify, configure a webhook callback to send run data to the webhook URL shown above</span>
            </li>
            <li className="flex gap-3">
              <span className="w-6 h-6 bg-violet-500/20 text-violet-400 rounded-full flex items-center justify-center text-xs font-medium flex-shrink-0">4</span>
              <span>Traces will automatically appear in your dashboard with failure detection</span>
            </li>
          </ol>
        </div>
      </div>
    </Layout>
  )
}
