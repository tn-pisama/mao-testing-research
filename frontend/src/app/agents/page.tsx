'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Layout } from '@/components/common/Layout'
import {
  AgentCard,
  AgentOrchestrationView,
  AgentActivityFeed,
  AgentMetricsPanel,
  AgentComparisonView,
  AgentHealthDashboard,
  AgentMonitoringPanel,
} from '@/components/agents'
import { DemoControlsPanel } from '@/components/demo/DemoControlsPanel'
import { useDemoMode } from '@/hooks/useDemoMode'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/Tabs'
import {
  Grid3X3,
  Network,
  BarChart3,
  Heart,
  Activity,
  GitCompare,
  Sparkles,
} from 'lucide-react'

export default function AgentsPage() {
  const router = useRouter()
  const [activeAgentId, setActiveAgentId] = useState<string | undefined>()
  const [viewMode, setViewMode] = useState<
    'orchestration' | 'grid' | 'health' | 'monitoring' | 'comparison' | 'metrics'
  >('orchestration')
  const demo = useDemoMode({ autoSimulate: true })

  const handleAgentClick = (agentId: string) => {
    setActiveAgentId(agentId)
    router.push(`/agents/${agentId}`)
  }

  if (!demo.isLoaded) {
    return (
      <Layout>
        <div className="p-6">
          <div className="animate-pulse space-y-6">
            <div className="h-8 w-64 bg-slate-700 rounded" />
            <div className="grid grid-cols-4 gap-4">
              {[1,2,3,4].map(i => <div key={i} className="h-24 bg-slate-700 rounded-xl" />)}
            </div>
            <div className="h-96 bg-slate-700 rounded-xl" />
          </div>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h1 className="text-2xl font-bold text-white">Agent Orchestration</h1>
              <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-gradient-to-r from-purple-500/20 to-pink-500/20 border border-purple-500/30 text-purple-400">
                <Sparkles size={10} className="inline mr-1" />
                Demo Mode
              </span>
            </div>
            <p className="text-sm text-slate-400">
              Real-time visualization and monitoring of multi-agent system execution
            </p>
          </div>
          <DemoControlsPanel
            isSimulating={demo.isSimulating}
            onToggleSimulation={demo.toggleSimulation}
            onRefresh={demo.refreshData}
          />
        </div>

        <AgentMetricsPanel metrics={demo.agentMetrics} />

        <div className="mt-6">
          <Tabs value={viewMode} onValueChange={(v) => setViewMode(v as typeof viewMode)}>
            <div className="flex items-center justify-between mb-4">
              <TabsList>
                <TabsTrigger value="orchestration">
                  <Network size={16} className="mr-2" />
                  Orchestration
                </TabsTrigger>
                <TabsTrigger value="grid">
                  <Grid3X3 size={16} className="mr-2" />
                  Grid
                </TabsTrigger>
                <TabsTrigger value="health">
                  <Heart size={16} className="mr-2" />
                  Health
                </TabsTrigger>
                <TabsTrigger value="monitoring">
                  <Activity size={16} className="mr-2" />
                  Monitoring
                </TabsTrigger>
                <TabsTrigger value="comparison">
                  <GitCompare size={16} className="mr-2" />
                  Compare
                </TabsTrigger>
                <TabsTrigger value="metrics">
                  <BarChart3 size={16} className="mr-2" />
                  Details
                </TabsTrigger>
              </TabsList>
            </div>

            <TabsContent value="orchestration" className="mt-4">
              <div className="grid lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2">
                  <AgentOrchestrationView
                    agents={demo.agents}
                    messages={demo.messages}
                    activeAgentId={activeAgentId}
                    onAgentClick={handleAgentClick}
                  />
                </div>
                <div>
                  <AgentActivityFeed
                    events={demo.activityEvents}
                    isLive={demo.isSimulating}
                    maxHeight="560px"
                  />
                </div>
              </div>
            </TabsContent>

            <TabsContent value="grid" className="mt-4">
              <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {demo.agents.map((agent) => (
                  <AgentCard
                    key={agent.id}
                    agent={agent}
                    isActive={agent.id === activeAgentId}
                    onClick={() => handleAgentClick(agent.id)}
                  />
                ))}
              </div>
              <div className="mt-6">
                <AgentActivityFeed
                  events={demo.activityEvents}
                  isLive={demo.isSimulating}
                />
              </div>
            </TabsContent>

            <TabsContent value="health" className="mt-4">
              <AgentHealthDashboard agents={demo.agents} />
            </TabsContent>

            <TabsContent value="monitoring" className="mt-4">
              <AgentMonitoringPanel isLive={demo.isSimulating} />
            </TabsContent>

            <TabsContent value="comparison" className="mt-4">
              <AgentComparisonView agents={demo.agents} />
            </TabsContent>

            <TabsContent value="metrics" className="mt-4">
              <div className="grid lg:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-white">Agent Details</h3>
                  <p className="text-sm text-slate-400 mb-4">
                    Click on an agent to view detailed performance metrics
                  </p>
                  {demo.agents.map((agent) => (
                    <AgentCard
                      key={agent.id}
                      agent={agent}
                      isActive={agent.id === activeAgentId}
                      onClick={() => handleAgentClick(agent.id)}
                    />
                  ))}
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-white mb-4">Activity Timeline</h3>
                  <AgentActivityFeed
                    events={demo.activityEvents}
                    isLive={demo.isSimulating}
                    maxHeight="800px"
                  />
                </div>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </Layout>
  )
}
