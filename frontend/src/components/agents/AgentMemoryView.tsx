'use client'

import { Card } from '../ui/Card'
import { Brain } from 'lucide-react'

export function AgentMemoryView({ agent: _agent, memory: _memory }: { agent?: unknown; memory?: unknown }) {
  return (
    <Card>
      <div className="text-center py-12 text-zinc-400">
        <Brain size={32} className="mx-auto mb-3 opacity-50" />
        <p className="text-sm">No memory data available</p>
        <p className="text-xs mt-1">Agent memory will be displayed here</p>
      </div>
    </Card>
  )
}
