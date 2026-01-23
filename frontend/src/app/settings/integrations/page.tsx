'use client'

export const dynamic = 'force-dynamic'

import { useState } from 'react'
import { Layout } from '@/components/common/Layout'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import {
  Box,
  ArrowLeft,
  CheckCircle,
  XCircle,
  Settings,
  ExternalLink,
  Webhook,
  MessageSquare,
  Bell,
  BarChart2,
  Database,
  GitBranch,
  RefreshCw,
} from 'lucide-react'
import Link from 'next/link'
import clsx from 'clsx'

interface Integration {
  id: string
  name: string
  description: string
  icon: React.ElementType
  status: 'connected' | 'disconnected' | 'error'
  lastSync?: string
  configurable: boolean
}

const integrations: Integration[] = [
  {
    id: 'slack',
    name: 'Slack',
    description: 'Send alerts and notifications to Slack channels',
    icon: MessageSquare,
    status: 'connected',
    lastSync: '2 minutes ago',
    configurable: true,
  },
  {
    id: 'pagerduty',
    name: 'PagerDuty',
    description: 'Trigger incidents for critical detections',
    icon: Bell,
    status: 'disconnected',
    configurable: true,
  },
  {
    id: 'datadog',
    name: 'Datadog',
    description: 'Export metrics and traces to Datadog APM',
    icon: BarChart2,
    status: 'connected',
    lastSync: '5 minutes ago',
    configurable: true,
  },
  {
    id: 'webhook',
    name: 'Webhooks',
    description: 'Send events to custom HTTP endpoints',
    icon: Webhook,
    status: 'connected',
    lastSync: '1 hour ago',
    configurable: true,
  },
  {
    id: 'langsmith',
    name: 'LangSmith',
    description: 'Import traces from LangSmith for analysis',
    icon: Database,
    status: 'disconnected',
    configurable: true,
  },
  {
    id: 'github',
    name: 'GitHub',
    description: 'Create issues and PRs for auto-healing suggestions',
    icon: GitBranch,
    status: 'disconnected',
    configurable: true,
  },
]

function StatusBadge({ status }: { status: Integration['status'] }) {
  switch (status) {
    case 'connected':
      return (
        <span className="flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-emerald-500/20 text-emerald-400">
          <CheckCircle size={12} />
          Connected
        </span>
      )
    case 'disconnected':
      return (
        <span className="flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-slate-500/20 text-slate-400">
          <XCircle size={12} />
          Not Connected
        </span>
      )
    case 'error':
      return (
        <span className="flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-red-500/20 text-red-400">
          <XCircle size={12} />
          Error
        </span>
      )
  }
}

export default function IntegrationsPage() {
  const [localIntegrations, setLocalIntegrations] = useState(integrations)
  const [configModal, setConfigModal] = useState<string | null>(null)
  const [testing, setTesting] = useState<string | null>(null)

  const handleToggle = (id: string) => {
    setLocalIntegrations(prev =>
      prev.map(int =>
        int.id === id
          ? {
              ...int,
              status: int.status === 'connected' ? 'disconnected' : 'connected',
              lastSync: int.status === 'disconnected' ? 'Just now' : undefined,
            }
          : int
      )
    )
  }

  const handleTest = async (id: string) => {
    setTesting(id)
    await new Promise(resolve => setTimeout(resolve, 1500))
    setTesting(null)
  }

  return (
    <Layout>
      <div className="p-6 max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-4 mb-6">
          <Link
            href="/settings"
            className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
          >
            <ArrowLeft size={20} />
          </Link>
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-1">
              <div className="p-2 bg-purple-600/20 rounded-lg">
                <Box className="w-5 h-5 text-purple-400" />
              </div>
              <h1 className="text-2xl font-bold text-white">Integrations</h1>
            </div>
            <p className="text-slate-400 text-sm">
              Connect PISAMA to your favorite tools and services
            </p>
          </div>
        </div>

        {/* Integrations List */}
        <div className="space-y-4">
          {localIntegrations.map((integration) => {
            const Icon = integration.icon
            const isConnected = integration.status === 'connected'

            return (
              <Card key={integration.id}>
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className={clsx(
                        'p-3 rounded-lg',
                        isConnected ? 'bg-slate-700' : 'bg-slate-800'
                      )}>
                        <Icon size={24} className={isConnected ? 'text-white' : 'text-slate-500'} />
                      </div>
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="text-white font-semibold">{integration.name}</h3>
                          <StatusBadge status={integration.status} />
                        </div>
                        <p className="text-sm text-slate-400">{integration.description}</p>
                        {integration.lastSync && (
                          <p className="text-xs text-slate-500 mt-1">
                            Last synced: {integration.lastSync}
                          </p>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      {isConnected && (
                        <>
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => handleTest(integration.id)}
                            loading={testing === integration.id}
                            leftIcon={<RefreshCw size={14} />}
                          >
                            Test
                          </Button>
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => setConfigModal(integration.id)}
                            leftIcon={<Settings size={14} />}
                          >
                            Configure
                          </Button>
                        </>
                      )}
                      <Button
                        variant={isConnected ? 'secondary' : 'primary'}
                        size="sm"
                        onClick={() => handleToggle(integration.id)}
                      >
                        {isConnected ? 'Disconnect' : 'Connect'}
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>

        {/* Custom Webhook Section */}
        <div className="mt-8">
          <h3 className="text-lg font-semibold text-white mb-4">Custom Webhooks</h3>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-400 mb-2">
                    Configure custom webhooks to receive events
                  </p>
                  <div className="text-xs text-slate-500">
                    Send detection events to any HTTP endpoint
                  </div>
                </div>
                <Button
                  variant="secondary"
                  leftIcon={<Webhook size={16} />}
                  onClick={() => setConfigModal('webhook')}
                >
                  Add Webhook
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Documentation */}
        <div className="mt-8 p-6 bg-slate-800/50 rounded-xl border border-slate-700">
          <h3 className="text-lg font-semibold text-white mb-4">Integration Documentation</h3>
          <div className="grid md:grid-cols-2 gap-4">
            <Link
              href="/docs/webhooks"
              className="flex items-center justify-between p-4 bg-slate-900 rounded-lg hover:bg-slate-800 transition-colors"
            >
              <div className="flex items-center gap-3">
                <Webhook size={20} className="text-slate-400" />
                <div>
                  <div className="text-sm font-medium text-white">Webhook Events</div>
                  <div className="text-xs text-slate-400">Event types and payloads</div>
                </div>
              </div>
              <ExternalLink size={16} className="text-slate-500" />
            </Link>
            <Link
              href="/docs/integration"
              className="flex items-center justify-between p-4 bg-slate-900 rounded-lg hover:bg-slate-800 transition-colors"
            >
              <div className="flex items-center gap-3">
                <Box size={20} className="text-slate-400" />
                <div>
                  <div className="text-sm font-medium text-white">Integration Guide</div>
                  <div className="text-xs text-slate-400">Setup and configuration</div>
                </div>
              </div>
              <ExternalLink size={16} className="text-slate-500" />
            </Link>
          </div>
        </div>

        {/* Config Modal */}
        {configModal && (
          <ConfigureModal
            integrationId={configModal}
            integration={localIntegrations.find(i => i.id === configModal)}
            onClose={() => setConfigModal(null)}
          />
        )}
      </div>
    </Layout>
  )
}

interface ConfigureModalProps {
  integrationId: string
  integration?: Integration
  onClose: () => void
}

function ConfigureModal({ integrationId, integration, onClose }: ConfigureModalProps) {
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    await new Promise(resolve => setTimeout(resolve, 500))
    setSaving(false)
    onClose()
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" role="dialog" aria-modal="true" aria-labelledby="integration-config-title">
      <div className="bg-slate-800 rounded-xl p-6 border border-slate-700 w-full max-w-md">
        <h2 id="integration-config-title" className="text-lg font-semibold text-white mb-4">
          Configure {integration?.name || 'Webhook'}
        </h2>

        <div className="space-y-4">
          {integrationId === 'slack' && (
            <>
              <div>
                <label htmlFor="slack-webhook-url" className="text-sm font-medium text-slate-300 block mb-2">
                  Webhook URL
                </label>
                <input
                  id="slack-webhook-url"
                  type="text"
                  placeholder="https://hooks.slack.com/services/..."
                  aria-required="true"
                  className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-blue-500 focus:outline-none"
                />
              </div>
              <div>
                <label htmlFor="slack-channel" className="text-sm font-medium text-slate-300 block mb-2">
                  Channel
                </label>
                <input
                  id="slack-channel"
                  type="text"
                  defaultValue="#alerts"
                  className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-blue-500 focus:outline-none"
                />
              </div>
            </>
          )}

          {integrationId === 'webhook' && (
            <>
              <div>
                <label htmlFor="webhook-endpoint" className="text-sm font-medium text-slate-300 block mb-2">
                  Endpoint URL
                </label>
                <input
                  id="webhook-endpoint"
                  type="text"
                  placeholder="https://your-service.com/webhook"
                  aria-required="true"
                  className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-blue-500 focus:outline-none"
                />
              </div>
              <div>
                <label htmlFor="webhook-secret" className="text-sm font-medium text-slate-300 block mb-2">
                  Secret (optional)
                </label>
                <input
                  id="webhook-secret"
                  type="password"
                  placeholder="Signing secret for verification"
                  className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-blue-500 focus:outline-none"
                />
              </div>
            </>
          )}

          {integrationId === 'datadog' && (
            <>
              <div>
                <label htmlFor="datadog-api-key" className="text-sm font-medium text-slate-300 block mb-2">
                  API Key
                </label>
                <input
                  id="datadog-api-key"
                  type="password"
                  placeholder="Datadog API key"
                  aria-required="true"
                  className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-blue-500 focus:outline-none"
                />
              </div>
              <div>
                <label htmlFor="datadog-site" className="text-sm font-medium text-slate-300 block mb-2">
                  Site
                </label>
                <select id="datadog-site" className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-blue-500 focus:outline-none">
                  <option value="us1">US1 (datadoghq.com)</option>
                  <option value="us3">US3 (us3.datadoghq.com)</option>
                  <option value="us5">US5 (us5.datadoghq.com)</option>
                  <option value="eu1">EU1 (datadoghq.eu)</option>
                </select>
              </div>
            </>
          )}

          {!['slack', 'webhook', 'datadog'].includes(integrationId) && (
            <div className="text-center py-4 text-slate-400">
              <p className="text-sm">Additional configuration options are not yet available</p>
            </div>
          )}

          <div className="flex gap-3 pt-2">
            <Button
              onClick={handleSave}
              loading={saving}
              className="flex-1"
            >
              Save Configuration
            </Button>
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
