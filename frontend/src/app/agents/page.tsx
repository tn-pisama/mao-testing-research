import { getServerApiToken, serverFetch } from '@/lib/server-auth'
import { AgentsClient } from './AgentsClient'

interface AgentQuality {
  agent_id: string
  agent_name: string
  agent_type: string
  avg_score: number
  grade: string
  total_runs: number
  issues_count: number
  min_score: number
  max_score: number
}

export default async function AgentsPage() {
  const auth = await getServerApiToken()
  const data = auth
    ? await serverFetch<{ agents: AgentQuality[]; total: number }>(
        '/dashboard/agent-quality', auth
      )
    : null

  return <AgentsClient initialAgents={data?.agents ?? []} />
}
