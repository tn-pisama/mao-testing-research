'use client'

import { useCallback, useMemo } from 'react'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  Node,
  Edge,
  NodeTypes,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
} from 'reactflow'
import 'reactflow/dist/style.css'
import type { QualityAssessment } from '@/lib/api'
import { AgentNode } from './nodes/AgentNode'
import { StartEndNode } from './nodes/StartEndNode'
import {
  buildNodesFromAgents,
  buildEdgesFromHandoffs,
  applyDagreLayout,
} from '@/lib/workflow-layout'

interface WorkflowGraphViewProps {
  workflow: QualityAssessment
  handoffGraph?: Record<string, string[]>
  height?: number
  onNodeClick?: (nodeId: string) => void
}

const nodeTypes: NodeTypes = {
  agent: AgentNode,
  startEnd: StartEndNode,
}

export function WorkflowGraphView({
  workflow,
  handoffGraph,
  height = 600,
  onNodeClick,
}: WorkflowGraphViewProps) {
  // Build nodes and edges from workflow data
  const { initialNodes, initialEdges } = useMemo(() => {
    const pattern = workflow.orchestration_score?.detected_pattern
    const nodes = buildNodesFromAgents(workflow.agent_scores || [], pattern)
    const edges = buildEdgesFromHandoffs(handoffGraph, workflow.agent_scores, pattern)

    // Apply layout
    const layouted = applyDagreLayout(nodes, edges, {
      direction: 'TB',
      nodeWidth: 200,
      nodeHeight: 120,
      rankSeparation: 100,
      nodeSeparation: 80,
    })

    return {
      initialNodes: layouted.nodes,
      initialEdges: layouted.edges,
    }
  }, [workflow, handoffGraph])

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

  const handleNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      if (node.type === 'agent' && onNodeClick) {
        onNodeClick(node.id)
      }
    },
    [onNodeClick]
  )

  if (!workflow.agent_scores || workflow.agent_scores.length === 0) {
    return (
      <div
        className="flex items-center justify-center bg-slate-800 rounded-lg border border-slate-700"
        style={{ height }}
      >
        <div className="text-center py-12 px-4">
          <div className="text-4xl mb-4">📊</div>
          <p className="text-slate-400 mb-2">No workflow structure available</p>
          <p className="text-slate-500 text-sm">
            Workflow diagram will appear once agent data is available
          </p>
        </div>
      </div>
    )
  }

  return (
    <div
      className="bg-slate-900 rounded-lg border border-slate-700 overflow-hidden"
      style={{ height }}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.1}
        maxZoom={2}
        defaultEdgeOptions={{
          type: 'smoothstep',
          style: { stroke: '#64748b', strokeWidth: 2 },
        }}
        proOptions={{ hideAttribution: true }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={20}
          size={1}
          color="#334155"
        />
        <Controls className="bg-slate-800 border border-slate-700 rounded-lg" />
        <MiniMap
          className="bg-slate-800 border border-slate-700 rounded"
          nodeColor={(node) => {
            if (node.type === 'startEnd') return '#475569'
            const score = (node.data as any).score || 0
            if (score >= 0.9) return '#22c55e'
            if (score >= 0.8) return '#3b82f6'
            if (score >= 0.6) return '#f59e0b'
            return '#ef4444'
          }}
          maskColor="rgba(15, 23, 42, 0.8)"
        />
      </ReactFlow>
    </div>
  )
}
