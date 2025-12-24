'use client'

import { useState, useMemo } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { Layout } from '@/components/common/Layout'
import { AgentDetailHeader } from '@/components/agents/AgentDetailHeader'
import { AgentPerformanceChart } from '@/components/agents/AgentPerformanceChart'
import { AgentStateTimeline } from '@/components/agents/AgentStateTimeline'
import { AgentCommunicationLog } from '@/components/agents/AgentCommunicationLog'
import { AgentToolUsage } from '@/components/agents/AgentToolUsage'
import { AgentMemoryView } from '@/components/agents/AgentMemoryView'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/Tabs'
import { useDemoMode } from '@/hooks/useDemoMode'
import { ArrowLeft, Activity, MessageSquare, Wrench, Brain, Clock } from 'lucide-react'

export default function AgentDetailPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const [activeTab, setActiveTab] = useState('performance')
  const demo = useDemoMode({ autoSimulate: true })

  const agent = useMemo(() => {
    return demo.agents.find((a) => a.id === id) || demo.agents[0]
  }, [demo.agents, id])

  const agentEvents = useMemo(() => {
    return demo.activityEvents.filter((e) => e.agentId === agent?.id)
  }, [demo.activityEvents, agent])

  if (!agent) {
    return (
      <Layout>
        <div className="p-6 text-center">
          <p className="text-slate-400">Agent not found</p>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="p-6">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors mb-6"
        >
          <ArrowLeft size={16} />
          <span className="text-sm">Back to Agents</span>
        </button>

        <AgentDetailHeader agent={agent} isLive={demo.isSimulating} />

        <div className="mt-8">
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList>
              <TabsTrigger value="performance">
                <Activity size={16} className="mr-2" />
                Performance
              </TabsTrigger>
              <TabsTrigger value="timeline">
                <Clock size={16} className="mr-2" />
                Timeline
              </TabsTrigger>
              <TabsTrigger value="communication">
                <MessageSquare size={16} className="mr-2" />
                Communication
              </TabsTrigger>
              <TabsTrigger value="tools">
                <Wrench size={16} className="mr-2" />
                Tools
              </TabsTrigger>
              <TabsTrigger value="memory">
                <Brain size={16} className="mr-2" />
                Memory
              </TabsTrigger>
            </TabsList>

            <TabsContent value="performance" className="mt-6">
              <AgentPerformanceChart agent={agent} />
            </TabsContent>

            <TabsContent value="timeline" className="mt-6">
              <AgentStateTimeline events={agentEvents} />
            </TabsContent>

            <TabsContent value="communication" className="mt-6">
              <AgentCommunicationLog
                agentId={agent.id}
                messages={demo.messages}
                agents={demo.agents}
              />
            </TabsContent>

            <TabsContent value="tools" className="mt-6">
              <AgentToolUsage agent={agent} />
            </TabsContent>

            <TabsContent value="memory" className="mt-6">
              <AgentMemoryView agent={agent} />
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </Layout>
  )
}
