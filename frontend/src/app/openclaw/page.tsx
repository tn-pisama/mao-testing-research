'use client'

export const dynamic = 'force-dynamic'

import { useState } from 'react'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import {
  Bot, Plus, Copy, CheckCircle, Loader2, WifiOff, Globe, ChevronDown,
} from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { createApiClient } from '@/lib/api'
import { useOpenClawInstances, useOpenClawAgents } from '@/hooks/useApiWithFallback'

export default function OpenClawPage() {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()

  const { instances, isLoading: instancesLoading, isDemoMode } = useOpenClawInstances()
  const { agents, isLoading: agentsLoading } = useOpenClawAgents()

  const [showInstanceForm, setShowInstanceForm] = useState(false)
  const [showAgentForm, setShowAgentForm] = useState(false)
  const [isRegistering, setIsRegistering] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copiedUrl, setCopiedUrl] = useState<string | null>(null)

  // Instance form state
  const [instanceName, setInstanceName] = useState('')
  const [gatewayUrl, setGatewayUrl] = useState('')
  const [apiKey, setApiKey] = useState('')

  // Agent form state
  const [selectedInstanceId, setSelectedInstanceId] = useState('')
  const [agentKey, setAgentKey] = useState('')
  const [agentName, setAgentName] = useState('')
  const [model, setModel] = useState('')

  const isLoading = instancesLoading || agentsLoading
  const webhookUrl = 'https://api.mao-testing.com/api/v1/openclaw/webhook'

  const registerInstance = async () => {
    if (!instanceName.trim() || !gatewayUrl.trim() || !apiKey.trim()) {
      setError('Name, Gateway URL, and API Key are required')
      return
    }
    setIsRegistering(true)
    setError(null)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      await api.registerOpenClawInstance({ name: instanceName, gateway_url: gatewayUrl, api_key: apiKey })
      setShowInstanceForm(false)
      setInstanceName('')
      setGatewayUrl('')
      setApiKey('')
    } catch {
      setError('Failed to register instance. Please try again.')
    }
    setIsRegistering(false)
  }

  const registerAgent = async () => {
    if (!selectedInstanceId || !agentKey.trim()) {
      setError('Instance and Agent Key are required')
      return
    }
    setIsRegistering(true)
    setError(null)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      await api.registerOpenClawAgent({ instance_id: selectedInstanceId, agent_key: agentKey, agent_name: agentName || undefined, model: model || undefined })
      setShowAgentForm(false)
      setAgentKey('')
      setAgentName('')
      setModel('')
    } catch {
      setError('Failed to register agent. Please try again.')
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
              <div className="p-2 bg-cyan-600/20 rounded-lg">
                <Bot className="w-6 h-6 text-cyan-400" />
              </div>
              <h1 className="text-2xl font-bold text-white">OpenClaw Agents</h1>
              {isDemoMode && (
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-lg bg-amber-500/10 border border-amber-500/30">
                  <WifiOff size={14} className="text-amber-400" />
                  <span className="text-xs font-medium text-amber-200">Demo Mode</span>
                </div>
              )}
            </div>
            <p className="text-slate-400">
              Connect OpenClaw instances for multi-channel session monitoring
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Button
              onClick={() => setShowAgentForm(true)}
              variant="secondary"
              leftIcon={<Plus size={16} />}
              disabled={instances.length === 0}
            >
              Register Agent
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
        <div className="mb-6 p-4 bg-cyan-500/10 border border-cyan-500/30 rounded-xl">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-cyan-200">Webhook URL</p>
              <code className="text-sm text-cyan-300">{webhookUrl}</code>
            </div>
            <button
              onClick={() => copyToClipboard(webhookUrl)}
              className="p-2 text-cyan-300 hover:text-white transition-colors"
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
              <h2 className="text-lg font-semibold text-white mb-4">Add OpenClaw Instance</h2>
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-slate-300 block mb-2">Instance Name *</label>
                  <input type="text" value={instanceName} onChange={(e) => setInstanceName(e.target.value)}
                    placeholder="e.g., Production Gateway" className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-cyan-500 focus:outline-none" />
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-300 block mb-2">Gateway URL *</label>
                  <input type="text" value={gatewayUrl} onChange={(e) => setGatewayUrl(e.target.value)}
                    placeholder="https://gateway.openclaw.io" className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-cyan-500 focus:outline-none" />
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-300 block mb-2">API Key *</label>
                  <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)}
                    placeholder="oc_xxxxxxxxxx" className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-cyan-500 focus:outline-none" />
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

        {/* Register Agent Modal */}
        {showAgentForm && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-slate-800 rounded-xl p-6 border border-slate-700 w-full max-w-md">
              <h2 className="text-lg font-semibold text-white mb-4">Register OpenClaw Agent</h2>
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-slate-300 block mb-2">Instance *</label>
                  <div className="relative">
                    <select value={selectedInstanceId} onChange={(e) => setSelectedInstanceId(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-cyan-500 focus:outline-none appearance-none">
                      <option value="">Select instance...</option>
                      {instances.map((inst) => (
                        <option key={inst.id} value={inst.id}>{inst.name}</option>
                      ))}
                    </select>
                    <ChevronDown size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                  </div>
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-300 block mb-2">Agent Key *</label>
                  <input type="text" value={agentKey} onChange={(e) => setAgentKey(e.target.value)}
                    placeholder="e.g., support-agent" className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-cyan-500 focus:outline-none" />
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-300 block mb-2">Agent Name</label>
                  <input type="text" value={agentName} onChange={(e) => setAgentName(e.target.value)}
                    placeholder="e.g., Customer Support Agent" className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-cyan-500 focus:outline-none" />
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-300 block mb-2">Model</label>
                  <input type="text" value={model} onChange={(e) => setModel(e.target.value)}
                    placeholder="e.g., claude-sonnet-4-20250514" className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-cyan-500 focus:outline-none" />
                </div>
                {error && <p className="text-red-400 text-sm">{error}</p>}
                <div className="flex gap-3 pt-2">
                  <Button onClick={registerAgent} disabled={isRegistering} loading={isRegistering} className="flex-1">Register</Button>
                  <Button variant="secondary" onClick={() => { setShowAgentForm(false); setError(null) }} disabled={isRegistering}>Cancel</Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Instances & Agents List */}
        <div className="bg-slate-800 rounded-xl border border-slate-700">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
            </div>
          ) : instances.length === 0 ? (
            <div className="text-center py-12 px-4">
              <Bot className="w-12 h-12 text-slate-600 mx-auto mb-4" />
              <p className="text-slate-400 mb-2">No OpenClaw instances connected</p>
              <p className="text-slate-400 text-sm">Add an OpenClaw instance to start monitoring agent sessions</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-700">
              {instances.map((inst) => (
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
                        {inst.otel_enabled && <Badge variant="info" size="sm">OTEL</Badge>}
                        <Badge variant="default" size="sm">{inst.ingestion_mode}</Badge>
                      </div>
                      <div className="flex items-center gap-3 text-slate-400 text-sm">
                        <span className="flex items-center gap-1"><Globe size={12} />{inst.gateway_url}</span>
                        {inst.channels_configured.length > 0 && (
                          <span>{inst.channels_configured.join(', ')}</span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Agents for this instance */}
                  {agents.length > 0 && (
                    <div className="mt-3 ml-4 space-y-2">
                      {agents.map((agent) => (
                        <div key={agent.id} className="p-3 bg-slate-900 rounded-lg flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="text-slate-300 text-sm">{agent.agent_name || agent.agent_key}</span>
                            {agent.model && <Badge variant="default" size="sm">{agent.model}</Badge>}
                            {agent.monitoring_enabled ? (
                              <Badge variant="success" size="sm">Monitoring</Badge>
                            ) : (
                              <Badge variant="default" size="sm">Paused</Badge>
                            )}
                          </div>
                          <div className="text-xs text-slate-400 flex items-center gap-4">
                            <span>{agent.total_sessions} sessions</span>
                            <span>{agent.total_messages} messages</span>
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
              <span className="w-6 h-6 bg-cyan-500/20 text-cyan-400 rounded-full flex items-center justify-center text-xs font-medium flex-shrink-0">1</span>
              <span>Add your OpenClaw gateway instance above with its URL and API key</span>
            </li>
            <li className="flex gap-3">
              <span className="w-6 h-6 bg-cyan-500/20 text-cyan-400 rounded-full flex items-center justify-center text-xs font-medium flex-shrink-0">2</span>
              <span>Register agents you want to monitor within the instance</span>
            </li>
            <li className="flex gap-3">
              <span className="w-6 h-6 bg-cyan-500/20 text-cyan-400 rounded-full flex items-center justify-center text-xs font-medium flex-shrink-0">3</span>
              <span>In your OpenClaw gateway config, add the webhook URL as a callback for session events</span>
            </li>
            <li className="flex gap-3">
              <span className="w-6 h-6 bg-cyan-500/20 text-cyan-400 rounded-full flex items-center justify-center text-xs font-medium flex-shrink-0">4</span>
              <span>Session traces will automatically appear with multi-agent failure detection</span>
            </li>
          </ol>
        </div>
      </div>
    </Layout>
  )
}
