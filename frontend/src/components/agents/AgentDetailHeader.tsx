'use client'

import { Card } from '../ui/Card'
import type { AgentInfo } from './index'

interface AgentDetailHeaderProps {
  agent?: AgentInfo
  isLive?: boolean
}

export function AgentDetailHeader({ agent, isLive }: AgentDetailHeaderProps) {
  return (
    <Card className="mb-6">
      <div className="p-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-white">{agent?.name || 'Agent'}</h2>
            <p className="text-sm text-zinc-400">{agent?.type || 'worker'}</p>
          </div>
          {isLive && (
            <span className="px-2 py-1 text-xs bg-green-500/20 text-green-400 rounded-full">
              Live
            </span>
          )}
        </div>
      </div>
    </Card>
  )
}
