'use client'

import { useState } from 'react'
import { Layout } from '@/components/common/Layout'
import { AgentCard, AgentOrchestrationView, AgentActivityFeed, AgentMetricsPanel } from '@/components/agents'
import { DemoControlsPanel } from '@/components/demo/DemoControlsPanel'
import { useDemoMode } from '@/hooks/useDemoMode'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/Tabs'
import { Grid3X3, Network, BarChart3 } from 'lucide-react'

export default function AgentsPage() {
  const [activeAgentId, setActiveAgentId] = useState<string | undefined>()
  const [viewMode, setViewMode] = useState<'grid' | 'orchestration' | 'metrics'>('orchestration')
  const demo = useDemoMode({ autoSimulate: true })

  return (
    <Layout>
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white">Agent Orchestration</h1>
            <p className="text-sm text-slate-400 mt-1">
              Real-time visualization of multi-agent system execution
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
            <TabsList>
              <TabsTrigger value="orchestration">
                <Network size={16} className="mr-2" />
                Orchestration
              </TabsTrigger>
              <TabsTrigger value="grid">
                <Grid3X3 size={16} className="mr-2" />
                Grid View
              </TabsTrigger>
              <TabsTrigger value="metrics">
                <BarChart3 size={16} className="mr-2" />
                Details
              </TabsTrigger>
            </TabsList>

            <TabsContent value="orchestration" className="mt-4">
              <div className="grid lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2">
                  <AgentOrchestrationView
                    agents={demo.agents}
                    messages={demo.messages}
                    activeAgentId={activeAgentId}
                    onAgentClick={setActiveAgentId}
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
                    onClick={() => setActiveAgentId(agent.id)}
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

            <TabsContent value="metrics" className="mt-4">
              <div className="grid lg:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-white">Agent Details</h3>
                  {demo.agents.map((agent) => (
                    <AgentCard
                      key={agent.id}
                      agent={agent}
                      isActive={agent.id === activeAgentId}
                      onClick={() => setActiveAgentId(agent.id)}
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
