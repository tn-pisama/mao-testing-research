'use client'

import { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { MessageSquare, AlertTriangle, CheckCircle, ArrowRight } from 'lucide-react'
import { clsx } from 'clsx'

type MessageType = 'task' | 'result' | 'error' | 'delegation'

interface MessageNodeData {
  type: MessageType
  content: string
  timestamp: string
}

const typeConfig: Record<MessageType, { color: string; bgColor: string; icon: typeof MessageSquare }> = {
  task: { color: 'text-blue-400', bgColor: 'bg-blue-500/20', icon: ArrowRight },
  result: { color: 'text-emerald-400', bgColor: 'bg-emerald-500/20', icon: CheckCircle },
  error: { color: 'text-red-400', bgColor: 'bg-red-500/20', icon: AlertTriangle },
  delegation: { color: 'text-purple-400', bgColor: 'bg-purple-500/20', icon: MessageSquare },
}

function MessageNodeComponent({ data }: NodeProps<MessageNodeData>) {
  const { type, content, timestamp } = data
  const config = typeConfig[type]
  const Icon = config.icon

  return (
    <>
      <Handle type="target" position={Position.Left} className="!bg-slate-500" />
      <div
        className={clsx(
          'p-3 rounded-lg border max-w-[200px]',
          config.bgColor,
          'border-slate-700'
        )}
      >
        <div className="flex items-center gap-2 mb-1">
          <Icon size={14} className={config.color} />
          <span className={clsx('text-xs font-medium capitalize', config.color)}>{type}</span>
        </div>
        <p className="text-xs text-slate-300 line-clamp-2">{content}</p>
        <div className="text-[10px] text-slate-500 mt-1">{timestamp}</div>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-slate-500" />
    </>
  )
}

export const MessageNode = memo(MessageNodeComponent)
