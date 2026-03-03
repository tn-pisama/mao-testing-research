'use client'

import { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'

interface DecisionNodeData {
  label: string
  condition?: string
}

export const DecisionNode = memo(({ data }: NodeProps<DecisionNodeData>) => {
  return (
    <div className="relative">
      <Handle
        type="target"
        position={Position.Top}
        className="w-3 h-3 !bg-zinc-600 !border-2 !border-zinc-400"
      />

      {/* Diamond shape */}
      <div className="relative w-32 h-32 flex items-center justify-center">
        <div className="absolute inset-0 rotate-45 bg-purple-600 border-2 border-purple-400 rounded-lg shadow-lg" />
        <div className="relative z-10 text-center px-2">
          <div className="font-semibold text-white text-sm mb-1">{data.label}</div>
          {data.condition && (
            <div className="text-xs text-purple-200">{data.condition}</div>
          )}
        </div>
      </div>

      {/* Multiple output handles for branching */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="true"
        className="w-3 h-3 !bg-green-500 !border-2 !border-green-400"
        style={{ left: '35%' }}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="false"
        className="w-3 h-3 !bg-red-500 !border-2 !border-red-400"
        style={{ left: '65%' }}
      />
    </div>
  )
})

DecisionNode.displayName = 'DecisionNode'
