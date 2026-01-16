'use client'

import { Card } from '../ui/Card'
import clsx from 'clsx'
import type { AgentInfo } from './index'

interface AgentCardProps {
  agent?: AgentInfo
  onClick?: () => void
  isActive?: boolean
}

export function AgentCard({ agent, onClick, isActive }: AgentCardProps) {
  return (
    <Card
      className={clsx(
        'cursor-pointer hover:bg-slate-800',
        isActive && 'ring-2 ring-blue-500'
      )}
      onClick={onClick}
    >
      <div className="p-4">
        <div className="text-lg font-medium text-white">{agent?.name || 'Agent'}</div>
        <div className="text-sm text-slate-400">{agent?.type || 'worker'}</div>
      </div>
    </Card>
  )
}
