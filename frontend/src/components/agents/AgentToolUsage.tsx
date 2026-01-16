'use client'

import { Card } from '../ui/Card'

export function AgentToolUsage({ agent, tools }: { agent?: unknown; tools?: unknown[] }) {
  return (
    <Card>
      <div className="text-center py-8 text-slate-400">
        <p className="text-sm">Tool usage coming soon</p>
      </div>
    </Card>
  )
}
