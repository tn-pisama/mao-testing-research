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
import { DecisionNode } from './nodes/DecisionNode'
import {
  buildNodesFromAgents,
  buildEdgesFromHandoffs,
  applyDagreLayout,
  type HandoffMetrics,
} from '@/lib/workflow-layout'

interface WorkflowGraphViewProps {
  workflow: QualityAssessment
  handoffGraph?: Record<string, string[]>
  handoffMetrics?: Record<string, HandoffMetrics>
  height?: number
  onNodeClick?: (nodeId: string) => void
  onEdgeClick?: (edgeId: string) => void
  exportRef?: React.RefObject<HTMLDivElement>
}

const nodeTypes: NodeTypes = {
  agent: AgentNode,
  startEnd: StartEndNode,
  decision: DecisionNode,
}

export function WorkflowGraphView({
  workflow,
  handoffGraph,
  handoffMetrics,
  height = 600,
  onNodeClick,
  onEdgeClick,
  exportRef,
}: WorkflowGraphViewProps) {
  // Build nodes and edges from workflow data
  const { initialNodes, initialEdges } = useMemo(() => {
    const pattern = workflow.orchestration_score?.detected_pattern
    const nodes = buildNodesFromAgents(workflow.agent_scores || [], pattern)
    const edges = buildEdgesFromHandoffs(handoffGraph, workflow.agent_scores, pattern, handoffMetrics)

    // Pattern-specific layout parameters
    let layoutOptions: Parameters<typeof applyDagreLayout>[2] = {
      direction: 'TB',
      nodeWidth: 200,
      nodeHeight: 120,
      rankSeparation: 100,
      nodeSeparation: 80,
    }

    if (pattern === 'fan-out' || pattern === 'conditional') {
      // Wider spacing for branching patterns
      layoutOptions = {
        ...layoutOptions,
        nodeSeparation: 120,
        rankSeparation: 120,
      }
    } else if (pattern === 'parallel') {
      // Side-by-side layout for parallel execution
      layoutOptions = {
        ...layoutOptions,
        direction: 'TB',
        nodeSeparation: 150,
        rankSeparation: 80,
      }
    } else if (pattern === 'hierarchical') {
      // Tighter vertical spacing for hierarchical
      layoutOptions = {
        ...layoutOptions,
        rankSeparation: 80,
        nodeSeparation: 60,
      }
    }

    // Apply layout
    const layouted = applyDagreLayout(nodes, edges, layoutOptions)

    return {
      initialNodes: layouted.nodes,
      initialEdges: layouted.edges,
    }
  }, [workflow, handoffGraph, handoffMetrics])

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

  const handleEdgeClick = useCallback(
    (_event: React.MouseEvent, edge: Edge) => {
      if (onEdgeClick) {
        onEdgeClick(edge.id)
      }
    },
    [onEdgeClick]
  )

  if (!workflow.agent_scores || workflow.agent_scores.length === 0) {
    return (
      <div
        className="flex items-center justify-center bg-zinc-800 rounded-lg border border-zinc-700"
        style={{ height }}
      >
        <div className="text-center py-12 px-4">
          <div className="text-4xl mb-4">📊</div>
          <p className="text-zinc-400 mb-2">No workflow structure available</p>
          <p className="text-zinc-500 text-sm">
            Workflow diagram will appear once agent data is available
          </p>
        </div>
      </div>
    )
  }

  return (
    <div
      ref={exportRef}
      className="bg-zinc-900 rounded-lg border border-zinc-700 overflow-hidden"
      style={{ height }}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        onEdgeClick={handleEdgeClick}
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
        <Controls className="bg-zinc-800 border border-zinc-700 rounded-lg" />
        <MiniMap
          className="bg-zinc-800 border border-zinc-700 rounded"
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
