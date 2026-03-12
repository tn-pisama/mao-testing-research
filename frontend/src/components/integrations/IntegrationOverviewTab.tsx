import { cn } from '@/lib/utils'
import {
  GitBranch,
  Bot,
  Workflow,
  Network,
  CheckCircle,
  XCircle,
} from 'lucide-react'
import type {
  N8nWorkflow,
  OpenClawInstance,
  OpenClawAgent,
  DifyInstance,
  DifyApp,
  LangGraphDeployment,
  LangGraphAssistant,
} from '@/lib/api'

type TabId = 'overview' | 'n8n' | 'openclaw' | 'dify' | 'langgraph'

export function IntegrationOverviewTab({
  n8nWorkflows,
  openclawInstances,
  openclawAgents,
  difyInstances,
  difyApps,
  langGraphDeployments,
  langGraphAssistants,
  onTabChange,
}: {
  n8nWorkflows: N8nWorkflow[]
  openclawInstances: OpenClawInstance[]
  openclawAgents: OpenClawAgent[]
  difyInstances: DifyInstance[]
  difyApps: DifyApp[]
  langGraphDeployments: LangGraphDeployment[]
  langGraphAssistants: LangGraphAssistant[]
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
    {
      id: 'langgraph' as TabId,
      name: 'LangGraph',
      icon: Network,
      color: 'text-emerald-400',
      bgColor: 'bg-emerald-500/10',
      borderColor: 'border-emerald-500/30',
      entityCount: langGraphDeployments.length,
      entityLabel: `deployments, ${langGraphAssistants.length} assistants`,
      connected: langGraphDeployments.length > 0,
    },
  ]

  const totalEntities = n8nWorkflows.length + openclawInstances.length + difyInstances.length + langGraphDeployments.length
  const connectedCount = providers.filter(p => p.connected).length

  return (
    <div className="space-y-8">
      {/* Provider Cards */}
      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
        {providers.map((p) => {
          const Icon = p.icon
          return (
            <button
              key={p.id}
              onClick={() => onTabChange(p.id)}
              className={cn(
                'p-6 rounded-xl border text-left transition-all hover:scale-[1.02]',
                p.bgColor,
                p.borderColor
              )}
            >
              <div className="flex items-center gap-3 mb-4">
                <div className={cn('p-2 rounded-lg', p.bgColor)}>
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
                        <XCircle size={12} className="text-zinc-500" />
                        <span className="text-xs text-zinc-500">Not configured</span>
                      </>
                    )}
                  </div>
                </div>
              </div>
              <div className="text-sm text-zinc-300">
                {p.entityCount} {p.entityLabel}
              </div>
            </button>
          )
        })}
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-zinc-800 border border-zinc-700 rounded-xl p-5">
          <div className="text-sm text-zinc-400 mb-1">Connected Platforms</div>
          <div className="text-2xl font-bold text-white">{connectedCount}<span className="text-zinc-500 text-base font-normal">/{providers.length}</span></div>
        </div>
        <div className="bg-zinc-800 border border-zinc-700 rounded-xl p-5">
          <div className="text-sm text-zinc-400 mb-1">Total Resources</div>
          <div className="text-2xl font-bold text-white">{totalEntities}</div>
        </div>
        <div className="bg-zinc-800 border border-zinc-700 rounded-xl p-5">
          <div className="text-sm text-zinc-400 mb-1">Monitored Agents</div>
          <div className="text-2xl font-bold text-white">{openclawAgents.length + langGraphAssistants.length + difyApps.length}</div>
        </div>
      </div>

      {/* Quick Start */}
      <div className="bg-zinc-800/50 border border-zinc-700 rounded-xl p-6">
        <h3 className="text-base font-semibold text-white mb-4">Quick Start</h3>
        <div className="grid md:grid-cols-2 gap-4">
          <div className="flex items-start gap-3">
            <div className="w-7 h-7 bg-blue-500/20 text-blue-400 rounded-full flex items-center justify-center text-xs font-medium flex-shrink-0 mt-0.5">1</div>
            <div>
              <p className="text-sm font-medium text-zinc-200">Connect a platform</p>
              <p className="text-xs text-zinc-400 mt-0.5">Click any provider above to add your first integration</p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <div className="w-7 h-7 bg-blue-500/20 text-blue-400 rounded-full flex items-center justify-center text-xs font-medium flex-shrink-0 mt-0.5">2</div>
            <div>
              <p className="text-sm font-medium text-zinc-200">Configure webhook</p>
              <p className="text-xs text-zinc-400 mt-0.5">Point your platform&apos;s callbacks to the Pisama webhook URL</p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <div className="w-7 h-7 bg-blue-500/20 text-blue-400 rounded-full flex items-center justify-center text-xs font-medium flex-shrink-0 mt-0.5">3</div>
            <div>
              <p className="text-sm font-medium text-zinc-200">Monitor traces</p>
              <p className="text-xs text-zinc-400 mt-0.5">Traces appear automatically on your dashboard with failure detection</p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <div className="w-7 h-7 bg-blue-500/20 text-blue-400 rounded-full flex items-center justify-center text-xs font-medium flex-shrink-0 mt-0.5">4</div>
            <div>
              <p className="text-sm font-medium text-zinc-200">Get quality scores</p>
              <p className="text-xs text-zinc-400 mt-0.5">Each workflow gets continuous quality grades with improvement suggestions</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
