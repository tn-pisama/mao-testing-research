'use client'

export const dynamic = 'force-dynamic'

import { useState, useEffect, useCallback } from 'react'
import { Layout } from '@/components/common/Layout'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { clsx } from 'clsx'
import {
  GitBranch,
  Bot,
  Workflow,
  Plus,
  RefreshCw,
  CheckCircle,
  XCircle,
  Activity,
  Globe,
  Key,
} from 'lucide-react'
import { createApiClient } from '@/lib/api'
import type {
  N8nWorkflow,
  OpenClawInstance,
  OpenClawAgent,
  DifyInstance,
  DifyApp,
} from '@/lib/api'
import { useSafeAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import {
  generateDemoApiN8nWorkflows,
  generateDemoOpenClawInstances,
  generateDemoOpenClawAgents,
  generateDemoDifyInstances,
  generateDemoDifyApps,
} from '@/lib/demo-data'

type TabId = 'overview' | 'n8n' | 'openclaw' | 'dify'

const tabs: { id: TabId; label: string; icon: React.ElementType }[] = [
  { id: 'overview', label: 'Overview', icon: Activity },
  { id: 'n8n', label: 'n8n', icon: GitBranch },
  { id: 'openclaw', label: 'OpenClaw', icon: Bot },
  { id: 'dify', label: 'Dify', icon: Workflow },
]

export default function IntegrationsPage() {
  const [activeTab, setActiveTab] = useState<TabId>('overview')
  const { getToken } = useSafeAuth()
  const { tenantId } = useTenant()

  // n8n state
  const [n8nWorkflows, setN8nWorkflows] = useState<N8nWorkflow[]>([])
  // OpenClaw state
  const [openclawInstances, setOpenclawInstances] = useState<OpenClawInstance[]>([])
  const [openclawAgents, setOpenclawAgents] = useState<OpenClawAgent[]>([])
  // Dify state
  const [difyInstances, setDifyInstances] = useState<DifyInstance[]>([])
  const [difyApps, setDifyApps] = useState<DifyApp[]>([])

  const [isLoading, setIsLoading] = useState(true)

  const loadData = useCallback(async () => {
    try {
      setIsLoading(true)
      const token = await getToken()
      if (!token || !tenantId) {
        // No auth — use demo data
        setN8nWorkflows(generateDemoApiN8nWorkflows())
        setOpenclawInstances(generateDemoOpenClawInstances())
        setOpenclawAgents(generateDemoOpenClawAgents())
        setDifyInstances(generateDemoDifyInstances())
        setDifyApps(generateDemoDifyApps())
        return
      }
      const api = createApiClient(token, tenantId)

      const [workflows, instances, agents, dInstances, apps] = await Promise.allSettled([
        api.listN8nWorkflows(),
        api.listOpenClawInstances(),
        api.listOpenClawAgents(),
        api.listDifyInstances(),
        api.listDifyApps(),
      ])

      const wf = workflows.status === 'fulfilled' ? workflows.value : []
      const oci = instances.status === 'fulfilled' ? instances.value : []
      const oca = agents.status === 'fulfilled' ? agents.value : []
      const di = dInstances.status === 'fulfilled' ? dInstances.value : []
      const da = apps.status === 'fulfilled' ? apps.value : []

      // Use demo data as fallback when all API calls return empty
      const allEmpty = wf.length === 0 && oci.length === 0 && di.length === 0
      setN8nWorkflows(wf.length > 0 ? wf : allEmpty ? generateDemoApiN8nWorkflows() : wf)
      setOpenclawInstances(oci.length > 0 ? oci : allEmpty ? generateDemoOpenClawInstances() : oci)
      setOpenclawAgents(oca.length > 0 ? oca : allEmpty ? generateDemoOpenClawAgents() : oca)
      setDifyInstances(di.length > 0 ? di : allEmpty ? generateDemoDifyInstances() : di)
      setDifyApps(da.length > 0 ? da : allEmpty ? generateDemoDifyApps() : da)
    } catch {
      // API error — fall back to demo data
      setN8nWorkflows(generateDemoApiN8nWorkflows())
      setOpenclawInstances(generateDemoOpenClawInstances())
      setOpenclawAgents(generateDemoOpenClawAgents())
      setDifyInstances(generateDemoDifyInstances())
      setDifyApps(generateDemoDifyApps())
    } finally {
      setIsLoading(false)
    }
  }, [getToken, tenantId])

  useEffect(() => {
    loadData()
  }, [loadData])

  return (
    <Layout>
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white">Integrations</h1>
            <p className="text-sm text-slate-400 mt-1">
              Connect and manage your AI orchestration platforms
            </p>
          </div>
          <button
            onClick={loadData}
            className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-white text-sm transition-colors"
          >
            <RefreshCw size={14} />
            Refresh
          </button>
        </div>

        {/* Tab navigation */}
        <div className="flex gap-1 mb-6 border-b border-slate-700 pb-px">
          {tabs.map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={clsx(
                  'flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-t-lg transition-colors border-b-2 -mb-px',
                  activeTab === tab.id
                    ? 'text-primary-400 border-primary-500 bg-primary-500/10'
                    : 'text-slate-400 border-transparent hover:text-white hover:bg-slate-700/50'
                )}
              >
                <Icon size={16} />
                {tab.label}
              </button>
            )
          })}
        </div>

        {/* Tab content */}
        {isLoading ? (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-24 bg-slate-700 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : (
          <>
            {activeTab === 'overview' && (
              <OverviewTab
                n8nWorkflows={n8nWorkflows}
                openclawInstances={openclawInstances}
                openclawAgents={openclawAgents}
                difyInstances={difyInstances}
                difyApps={difyApps}
                onTabChange={setActiveTab}
              />
            )}
            {activeTab === 'n8n' && <N8nTab workflows={n8nWorkflows} />}
            {activeTab === 'openclaw' && (
              <OpenClawTab instances={openclawInstances} agents={openclawAgents} />
            )}
            {activeTab === 'dify' && <DifyTab instances={difyInstances} apps={difyApps} />}
          </>
        )}
      </div>
    </Layout>
  )
}

// --- Overview Tab ---

function OverviewTab({
  n8nWorkflows,
  openclawInstances,
  openclawAgents,
  difyInstances,
  difyApps,
  onTabChange,
}: {
  n8nWorkflows: N8nWorkflow[]
  openclawInstances: OpenClawInstance[]
  openclawAgents: OpenClawAgent[]
  difyInstances: DifyInstance[]
  difyApps: DifyApp[]
  onTabChange: (tab: TabId) => void
}) {
  const providers = [
    {
      id: 'n8n' as TabId,
      name: 'n8n',
      icon: GitBranch,
      color: 'text-orange-400',
      bgColor: 'bg-orange-500/10',
      borderColor: 'border-orange-500/30',
      entityCount: n8nWorkflows.length,
      entityLabel: 'workflows',
      connected: n8nWorkflows.length > 0,
    },
    {
      id: 'openclaw' as TabId,
      name: 'OpenClaw',
      icon: Bot,
      color: 'text-cyan-400',
      bgColor: 'bg-cyan-500/10',
      borderColor: 'border-cyan-500/30',
      entityCount: openclawInstances.length,
      entityLabel: `instances, ${openclawAgents.length} agents`,
      connected: openclawInstances.length > 0,
    },
    {
      id: 'dify' as TabId,
      name: 'Dify',
      icon: Workflow,
      color: 'text-violet-400',
      bgColor: 'bg-violet-500/10',
      borderColor: 'border-violet-500/30',
      entityCount: difyInstances.length,
      entityLabel: `instances, ${difyApps.length} apps`,
      connected: difyInstances.length > 0,
    },
  ]

  return (
    <div className="grid md:grid-cols-3 gap-4">
      {providers.map((p) => {
        const Icon = p.icon
        return (
          <button
            key={p.id}
            onClick={() => onTabChange(p.id)}
            className={clsx(
              'p-6 rounded-xl border text-left transition-all hover:scale-[1.02]',
              p.bgColor,
              p.borderColor
            )}
          >
            <div className="flex items-center gap-3 mb-4">
              <div className={clsx('p-2 rounded-lg', p.bgColor)}>
                <Icon size={24} className={p.color} />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-white">{p.name}</h3>
                <div className="flex items-center gap-1.5">
                  {p.connected ? (
                    <>
                      <CheckCircle size={12} className="text-green-400" />
                      <span className="text-xs text-green-400">Connected</span>
                    </>
                  ) : (
                    <>
                      <XCircle size={12} className="text-slate-500" />
                      <span className="text-xs text-slate-500">Not configured</span>
                    </>
                  )}
                </div>
              </div>
            </div>
            <div className="text-sm text-slate-300">
              {p.entityCount} {p.entityLabel}
            </div>
          </button>
        )
      })}
    </div>
  )
}

// --- N8n Tab ---

function N8nTab({ workflows }: { workflows: N8nWorkflow[] }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">n8n Workflows</h2>
        <a
          href="/n8n"
          className="flex items-center gap-2 px-4 py-2 bg-orange-600 hover:bg-orange-700 rounded-lg text-white text-sm transition-colors"
        >
          <Plus size={14} />
          Manage Workflows
        </a>
      </div>

      {workflows.length === 0 ? (
        <EmptyState
          icon={GitBranch}
          title="No n8n workflows registered"
          description="Register your n8n workflows to start monitoring executions."
        />
      ) : (
        <Card>
          <div className="divide-y divide-slate-700">
            {workflows.map((w) => (
              <div key={w.id} className="p-4 flex items-center justify-between">
                <div>
                  <div className="text-white font-medium">
                    {w.workflow_name || w.workflow_id}
                  </div>
                  <div className="text-xs text-slate-400 mt-1 flex items-center gap-3">
                    <span>ID: {w.workflow_id}</span>
                    {w.ingestion_mode && (
                      <Badge variant="default" size="sm">{w.ingestion_mode}</Badge>
                    )}
                  </div>
                </div>
                <div className="text-xs text-slate-500 flex items-center gap-2">
                  <Globe size={12} />
                  {w.webhook_url}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}

// --- OpenClaw Tab ---

function OpenClawTab({
  instances,
  agents,
}: {
  instances: OpenClawInstance[]
  agents: OpenClawAgent[]
}) {
  return (
    <div className="space-y-6">
      {/* Instances */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-4">OpenClaw Instances</h2>
        {instances.length === 0 ? (
          <EmptyState
            icon={Bot}
            title="No OpenClaw instances connected"
            description="Register an OpenClaw instance to monitor agent sessions."
          />
        ) : (
          <Card>
            <div className="divide-y divide-slate-700">
              {instances.map((inst) => (
                <div key={inst.id} className="p-4 flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-white font-medium">{inst.name}</span>
                      {inst.is_active ? (
                        <Badge variant="success" size="sm">Active</Badge>
                      ) : (
                        <Badge variant="default" size="sm">Inactive</Badge>
                      )}
                      {inst.otel_enabled && (
                        <Badge variant="info" size="sm">OTEL</Badge>
                      )}
                    </div>
                    <div className="text-xs text-slate-400 mt-1 flex items-center gap-3">
                      <span className="flex items-center gap-1">
                        <Globe size={12} />
                        {inst.gateway_url}
                      </span>
                      <Badge variant="default" size="sm">{inst.ingestion_mode}</Badge>
                    </div>
                  </div>
                  <div className="text-xs text-slate-500">
                    {inst.channels_configured.length > 0
                      ? inst.channels_configured.join(', ')
                      : 'No channels'}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>

      {/* Agents */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-4">Registered Agents</h2>
        {agents.length === 0 ? (
          <EmptyState
            icon={Key}
            title="No agents registered"
            description="Register agents within your OpenClaw instances for monitoring."
          />
        ) : (
          <Card>
            <div className="divide-y divide-slate-700">
              {agents.map((agent) => (
                <div key={agent.id} className="p-4 flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-white font-medium">
                        {agent.agent_name || agent.agent_key}
                      </span>
                      {agent.monitoring_enabled ? (
                        <Badge variant="success" size="sm">Monitoring</Badge>
                      ) : (
                        <Badge variant="default" size="sm">Paused</Badge>
                      )}
                    </div>
                    <div className="text-xs text-slate-400 mt-1 flex items-center gap-3">
                      <span>Key: {agent.agent_key}</span>
                      {agent.model && <span>Model: {agent.model}</span>}
                    </div>
                  </div>
                  <div className="text-right text-xs text-slate-400">
                    <div>{agent.total_sessions} sessions</div>
                    <div>{agent.total_messages} messages</div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}

// --- Dify Tab ---

function DifyTab({
  instances,
  apps,
}: {
  instances: DifyInstance[]
  apps: DifyApp[]
}) {
  return (
    <div className="space-y-6">
      {/* Instances */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-4">Dify Instances</h2>
        {instances.length === 0 ? (
          <EmptyState
            icon={Workflow}
            title="No Dify instances connected"
            description="Register a Dify instance to monitor workflow runs and app executions."
          />
        ) : (
          <Card>
            <div className="divide-y divide-slate-700">
              {instances.map((inst) => (
                <div key={inst.id} className="p-4 flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-white font-medium">{inst.name}</span>
                      {inst.is_active ? (
                        <Badge variant="success" size="sm">Active</Badge>
                      ) : (
                        <Badge variant="default" size="sm">Inactive</Badge>
                      )}
                    </div>
                    <div className="text-xs text-slate-400 mt-1 flex items-center gap-3">
                      <span className="flex items-center gap-1">
                        <Globe size={12} />
                        {inst.base_url}
                      </span>
                      <Badge variant="default" size="sm">{inst.ingestion_mode}</Badge>
                    </div>
                  </div>
                  <div className="text-xs text-slate-500">
                    {inst.app_types_configured.length > 0
                      ? inst.app_types_configured.join(', ')
                      : 'No app types'}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>

      {/* Apps */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-4">Registered Apps</h2>
        {apps.length === 0 ? (
          <EmptyState
            icon={Key}
            title="No apps registered"
            description="Register Dify apps within your instances for monitoring."
          />
        ) : (
          <Card>
            <div className="divide-y divide-slate-700">
              {apps.map((app) => (
                <div key={app.id} className="p-4 flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-white font-medium">
                        {app.app_name || app.app_id}
                      </span>
                      <Badge variant="info" size="sm">{app.app_type}</Badge>
                      {app.monitoring_enabled ? (
                        <Badge variant="success" size="sm">Monitoring</Badge>
                      ) : (
                        <Badge variant="default" size="sm">Paused</Badge>
                      )}
                    </div>
                    <div className="text-xs text-slate-400 mt-1">
                      App ID: {app.app_id}
                    </div>
                  </div>
                  <div className="text-right text-xs text-slate-400">
                    <div>{app.total_runs} runs</div>
                    <div>{app.total_tokens.toLocaleString()} tokens</div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}

// --- Shared ---

function EmptyState({
  icon: Icon,
  title,
  description,
}: {
  icon: React.ElementType
  title: string
  description: string
}) {
  return (
    <Card>
      <div className="text-center py-12 px-4">
        <Icon size={40} className="mx-auto mb-4 text-slate-600 opacity-50" />
        <p className="text-slate-300 mb-2 font-medium">{title}</p>
        <p className="text-sm text-slate-500">{description}</p>
      </div>
    </Card>
  )
}
