'use client'

import { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'

interface StartEndNodeData {
  label: string
  isStart: boolean
}

export const StartEndNode = memo(({ data }: NodeProps<StartEndNodeData>) => {
  return (
    <div className="px-6 py-3 rounded-full bg-slate-700 border-2 border-slate-500 min-w-[100px] text-center">
      {!data.isStart && (
        <Handle
          type="target"
          position={Position.Top}
          className="w-3 h-3 !bg-slate-600 !border-2 !border-slate-400"
        />
      )}

      <div className="font-semibold text-white text-sm">{data.label}</div>

      {data.isStart && (
        <Handle
          type="source"
          position={Position.Bottom}
          className="w-3 h-3 !bg-slate-600 !border-2 !border-slate-400"
        />
      )}
    </div>
  )
})

StartEndNode.displayName = 'StartEndNode'
