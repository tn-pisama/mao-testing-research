'use client'

export const dynamic = 'force-dynamic'

import { useState } from 'react'
import { Layout } from '@/components/common/Layout'
import { cn } from '@/lib/utils'
import {
  GitBranch,
  Bot,
  Workflow,
  Network,
  RefreshCw,
  Activity,
} from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import {
  useN8nWorkflowsQuery,
  useOpenClawInstancesQuery,
  useOpenClawAgentsQuery,
  useDifyInstancesQuery,
  useDifyAppsQuery,
  useLangGraphDeploymentsQuery,
  useLangGraphAssistantsQuery,
} from '@/hooks/useQueries'
import { IntegrationOverviewTab } from '@/components/integrations/IntegrationOverviewTab'
import { N8nIntegrationTab } from '@/components/integrations/N8nIntegrationTab'
import { OpenClawIntegrationTab } from '@/components/integrations/OpenClawIntegrationTab'
import { DifyIntegrationTab } from '@/components/integrations/DifyIntegrationTab'
import { LangGraphIntegrationTab } from '@/components/integrations/LangGraphIntegrationTab'

type TabId = 'overview' | 'n8n' | 'openclaw' | 'dify' | 'langgraph'

const tabs: { id: TabId; label: string; icon: React.ElementType }[] = [
  { id: 'overview', label: 'Overview', icon: Activity },
  { id: 'n8n', label: 'n8n', icon: GitBranch },
  { id: 'openclaw', label: 'OpenClaw', icon: Bot },
  { id: 'dify', label: 'Dify', icon: Workflow },
  { id: 'langgraph', label: 'LangGraph', icon: Network },
]

export default function IntegrationsPage() {
  const [activeTab, setActiveTab] = useState<TabId>('overview')
  const queryClient = useQueryClient()

  const { workflows: n8nWorkflows, isLoading: n8nLoading } = useN8nWorkflowsQuery()
  const { instances: openclawInstances, isLoading: ocInstLoading } = useOpenClawInstancesQuery()
  const { agents: openclawAgents, isLoading: ocAgentLoading } = useOpenClawAgentsQuery()
  const { instances: difyInstances, isLoading: difyInstLoading } = useDifyInstancesQuery()
  const { apps: difyApps, isLoading: difyAppLoading } = useDifyAppsQuery()
  const { deployments: langGraphDeployments, isLoading: lgDepLoading } = useLangGraphDeploymentsQuery()
  const { assistants: langGraphAssistants, isLoading: lgAsstLoading } = useLangGraphAssistantsQuery()

  const isLoading = n8nLoading || ocInstLoading || ocAgentLoading || difyInstLoading || difyAppLoading || lgDepLoading || lgAsstLoading

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['n8nWorkflows'] })
    queryClient.invalidateQueries({ queryKey: ['openClawInstances'] })
    queryClient.invalidateQueries({ queryKey: ['openClawAgents'] })
    queryClient.invalidateQueries({ queryKey: ['difyInstances'] })
    queryClient.invalidateQueries({ queryKey: ['difyApps'] })
    queryClient.invalidateQueries({ queryKey: ['langGraphDeployments'] })
    queryClient.invalidateQueries({ queryKey: ['langGraphAssistants'] })
  }

  return (
    <Layout>
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white">Integrations</h1>
            <p className="text-sm text-zinc-400 mt-1">
              Connect and manage your AI orchestration platforms
            </p>
          </div>
          <button
            onClick={handleRefresh}
            className="flex items-center gap-2 px-4 py-2 bg-zinc-700 hover:bg-zinc-600 rounded-lg text-white text-sm transition-colors"
          >
            <RefreshCw size={14} />
            Refresh
          </button>
        </div>

        {/* Tab navigation */}
        <div className="flex gap-1 mb-6 border-b border-zinc-700 pb-px">
          {tabs.map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-t-lg transition-colors border-b-2 -mb-px',
                  activeTab === tab.id
                    ? 'text-blue-400 border-blue-500 bg-blue-500/10'
                    : 'text-zinc-400 border-transparent hover:text-white hover:bg-zinc-700/50'
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
              <div key={i} className="h-24 bg-zinc-700 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : (
          <>
            {activeTab === 'overview' && (
              <IntegrationOverviewTab
                n8nWorkflows={n8nWorkflows}
                openclawInstances={openclawInstances}
                openclawAgents={openclawAgents}
                difyInstances={difyInstances}
                difyApps={difyApps}
                langGraphDeployments={langGraphDeployments}
                langGraphAssistants={langGraphAssistants}
                onTabChange={setActiveTab}
              />
            )}
            {activeTab === 'n8n' && <N8nIntegrationTab workflows={n8nWorkflows} />}
            {activeTab === 'openclaw' && (
              <OpenClawIntegrationTab instances={openclawInstances} agents={openclawAgents} />
            )}
            {activeTab === 'dify' && <DifyIntegrationTab instances={difyInstances} apps={difyApps} />}
            {activeTab === 'langgraph' && (
              <LangGraphIntegrationTab deployments={langGraphDeployments} assistants={langGraphAssistants} />
            )}
          </>
        )}
      </div>
    </Layout>
  )
}
