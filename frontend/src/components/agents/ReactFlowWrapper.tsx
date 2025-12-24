'use client'

import { memo } from 'react'
import ReactFlow, {
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { AgentNode } from './AgentNode'
import { MessageNode } from './MessageNode'

const nodeTypes = {
  agent: AgentNode,
  message: MessageNode,
}

interface ReactFlowWrapperProps {
  initialNodes: Node[]
  initialEdges: Edge[]
}

function ReactFlowWrapperComponent({ initialNodes, initialEdges }: ReactFlowWrapperProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

  return (
    <div className="h-[600px] bg-slate-900 rounded-xl border border-slate-700 overflow-hidden">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.5}
        maxZoom={1.5}
        defaultViewport={{ x: 0, y: 0, zoom: 0.8 }}
      >
        <Background color="#334155" gap={20} size={1} />
        <Controls className="bg-slate-800 border-slate-700 text-white" />
        <MiniMap
          nodeColor={(node) => {
            if (node.data?.agent?.status === 'running') return '#22c55e'
            if (node.data?.agent?.status === 'failed') return '#ef4444'
            return '#64748b'
          }}
          maskColor="rgba(15, 23, 42, 0.8)"
          className="bg-slate-800 border-slate-700"
        />
      </ReactFlow>
    </div>
  )
}

export default memo(ReactFlowWrapperComponent)
