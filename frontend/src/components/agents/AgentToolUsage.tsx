'use client'

import { Card } from '../ui/Card'
import { Wrench } from 'lucide-react'

export function AgentToolUsage({ agent, tools }: { agent?: unknown; tools?: unknown[] }) {
  return (
    <Card>
      <div className="text-center py-12 text-slate-400">
        <Wrench size={32} className="mx-auto mb-3 opacity-50" />
        <p className="text-sm">No tool usage recorded</p>
        <p className="text-xs mt-1">Tool invocations will be tracked here</p>
      </div>
    </Card>
  )
}
