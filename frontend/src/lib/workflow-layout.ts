import dagre from 'dagre'
import type { Node, Edge } from 'reactflow'
import type { AgentQualityScore } from './api'

export interface LayoutOptions {
  direction?: 'TB' | 'LR' // Top-to-bottom or Left-to-right
  nodeWidth?: number
  nodeHeight?: number
  rankSeparation?: number
  nodeSeparation?: number
}

export interface HandoffMetrics {
  successRate: number // 0-1
  avgLatencyMs: number
  totalHandoffs: number
  failedHandoffs: number
  status: 'healthy' | 'degraded' | 'failing'
}

const defaultOptions: Required<LayoutOptions> = {
  direction: 'TB',
  nodeWidth: 200,
  nodeHeight: 100,
  rankSeparation: 80,
  nodeSeparation: 60,
}

/**
 * Apply dagre layout algorithm to position nodes
 */
export function applyDagreLayout(
  nodes: Node[],
  edges: Edge[],
  options: LayoutOptions = {}
): { nodes: Node[]; edges: Edge[] } {
  const opts = { ...defaultOptions, ...options }

  const dagreGraph = new dagre.graphlib.Graph()
  dagreGraph.setDefaultEdgeLabel(() => ({}))
  dagreGraph.setGraph({
    rankdir: opts.direction,
    ranksep: opts.rankSeparation,
    nodesep: opts.nodeSeparation,
  })

  // Add nodes to dagre
  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, {
      width: opts.nodeWidth,
      height: opts.nodeHeight,
    })
  })

  // Add edges to dagre
  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target)
  })

  // Calculate layout
  dagre.layout(dagreGraph)

  // Apply positions to nodes
  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id)
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - opts.nodeWidth / 2,
        y: nodeWithPosition.y - opts.nodeHeight / 2,
      },
    }
  })

  return { nodes: layoutedNodes, edges }
}

/**
 * Build graph nodes from agent scores
 */
export function buildNodesFromAgents(
  agentScores: AgentQualityScore[],
  pattern?: string
): Node[] {
  const nodes: Node[] = []

  // Add Start node
  nodes.push({
    id: 'start',
    type: 'startEnd',
    data: { label: 'START', isStart: true },
    position: { x: 0, y: 0 },
  })

  // For conditional patterns, add a decision node after the first agent
  if (pattern === 'conditional' && agentScores.length >= 3) {
    // Add first agent
    if (agentScores[0]) {
      nodes.push({
        id: agentScores[0].agent_id,
        type: 'agent',
        data: {
          label: agentScores[0].agent_name,
          agentType: agentScores[0].agent_type,
          score: agentScores[0].overall_score,
          grade: agentScores[0].grade,
          issuesCount: agentScores[0].issues_count,
          criticalIssues: agentScores[0].critical_issues,
          hasIssues: agentScores[0].issues_count > 0,
          hasCritical: agentScores[0].critical_issues.length > 0,
        },
        position: { x: 0, y: 0 },
      })
    }

    // Add decision node
    nodes.push({
      id: 'decision-1',
      type: 'decision',
      data: {
        label: 'Route',
        condition: 'Conditional branching',
      },
      position: { x: 0, y: 0 },
    })

    // Add remaining agents (branches)
    agentScores.slice(1).forEach((agent) => {
      nodes.push({
        id: agent.agent_id,
        type: 'agent',
        data: {
          label: agent.agent_name,
          agentType: agent.agent_type,
          score: agent.overall_score,
          grade: agent.grade,
          issuesCount: agent.issues_count,
          criticalIssues: agent.critical_issues,
          hasIssues: agent.issues_count > 0,
          hasCritical: agent.critical_issues.length > 0,
        },
        position: { x: 0, y: 0 },
      })
    })
  } else {
    // Add all Agent nodes normally for other patterns
    agentScores.forEach((agent) => {
      nodes.push({
        id: agent.agent_id,
        type: 'agent',
        data: {
          label: agent.agent_name,
          agentType: agent.agent_type,
          score: agent.overall_score,
          grade: agent.grade,
          issuesCount: agent.issues_count,
          criticalIssues: agent.critical_issues,
          hasIssues: agent.issues_count > 0,
          hasCritical: agent.critical_issues.length > 0,
        },
        position: { x: 0, y: 0 },
      })
    })
  }

  // Add End node
  nodes.push({
    id: 'end',
    type: 'startEnd',
    data: { label: 'END', isStart: false },
    position: { x: 0, y: 0 },
  })

  return nodes
}

/**
 * Get edge color based on handoff status
 */
function getEdgeColor(metrics?: HandoffMetrics): string {
  if (!metrics) return '#64748b' // slate-500 (default)

  if (metrics.status === 'healthy') return '#22c55e' // green-500
  if (metrics.status === 'degraded') return '#f59e0b' // amber-500
  return '#ef4444' // red-500 (failing)
}

/**
 * Get edge stroke width based on handoff volume
 */
function getEdgeWidth(metrics?: HandoffMetrics): number {
  if (!metrics) return 2

  // Thicker edges for higher volume handoffs
  if (metrics.totalHandoffs > 50) return 3
  if (metrics.totalHandoffs > 20) return 2.5
  return 2
}

/**
 * Build graph edges from handoff data or infer from agent sequence
 */
export function buildEdgesFromHandoffs(
  handoffGraph?: Record<string, string[]>,
  agentScores?: AgentQualityScore[],
  pattern?: string,
  handoffMetrics?: Record<string, HandoffMetrics>
): Edge[] {
  const edges: Edge[] = []

  // If handoff graph provided, use it
  if (handoffGraph && Object.keys(handoffGraph).length > 0) {
    Object.entries(handoffGraph).forEach(([fromAgent, toAgents]) => {
      toAgents.forEach((toAgent) => {
        const edgeId = `${fromAgent}-${toAgent}`
        const metrics = handoffMetrics?.[edgeId]
        const color = getEdgeColor(metrics)
        const strokeWidth = getEdgeWidth(metrics)

        edges.push({
          id: edgeId,
          source: fromAgent,
          target: toAgent,
          type: 'smoothstep',
          animated: metrics?.status === 'healthy' && metrics.successRate > 0.95,
          style: {
            stroke: color,
            strokeWidth,
          },
          label: metrics ? `${(metrics.successRate * 100).toFixed(0)}% • ${metrics.avgLatencyMs}ms` : undefined,
          labelStyle: {
            fill: color,
            fontWeight: 500,
            fontSize: 11,
          },
          labelBgStyle: {
            fill: '#0f172a',
            fillOpacity: 0.8,
          },
        })
      })
    })
    return edges
  }

  // Fallback: Infer edges from agent sequence and pattern
  if (!agentScores || agentScores.length === 0) return edges

  const agentIds = agentScores.map((a) => a.agent_id)

  // Connect Start to first agent
  if (agentIds.length > 0) {
    edges.push({
      id: `start-${agentIds[0]}`,
      source: 'start',
      target: agentIds[0],
      type: 'smoothstep',
    })
  }

  // Pattern-based edge inference
  if (pattern === 'sequential' || !pattern) {
    // Sequential: A → B → C → D
    agentIds.forEach((agentId, idx) => {
      if (idx < agentIds.length - 1) {
        edges.push({
          id: `${agentId}-${agentIds[idx + 1]}`,
          source: agentId,
          target: agentIds[idx + 1],
          type: 'smoothstep',
        })
      }
    })
    // Connect last agent to End
    edges.push({
      id: `${agentIds[agentIds.length - 1]}-end`,
      source: agentIds[agentIds.length - 1],
      target: 'end',
      type: 'smoothstep',
    })
  } else if (pattern === 'fan-out' || pattern === 'parallel') {
    // Fan-out: A → [B, C, D] → E
    if (agentIds.length >= 3) {
      const firstAgent = agentIds[0]
      const middleAgents = agentIds.slice(1, -1)
      const lastAgent = agentIds[agentIds.length - 1]

      // First agent fans out to middle agents
      middleAgents.forEach((middleAgent) => {
        edges.push({
          id: `${firstAgent}-${middleAgent}`,
          source: firstAgent,
          target: middleAgent,
          type: 'smoothstep',
        })
      })

      // Middle agents converge to last agent
      middleAgents.forEach((middleAgent) => {
        edges.push({
          id: `${middleAgent}-${lastAgent}`,
          source: middleAgent,
          target: lastAgent,
          type: 'smoothstep',
        })
      })

      // Last agent to End
      edges.push({
        id: `${lastAgent}-end`,
        source: lastAgent,
        target: 'end',
        type: 'smoothstep',
      })
    } else {
      // Fallback to sequential if not enough agents
      agentIds.forEach((agentId, idx) => {
        if (idx < agentIds.length - 1) {
          edges.push({
            id: `${agentId}-${agentIds[idx + 1]}`,
            source: agentId,
            target: agentIds[idx + 1],
            type: 'smoothstep',
          })
        }
      })
      edges.push({
        id: `${agentIds[agentIds.length - 1]}-end`,
        source: agentIds[agentIds.length - 1],
        target: 'end',
        type: 'smoothstep',
      })
    }
  } else if (pattern === 'conditional') {
    // Conditional: A → Decision → [B, C] → D
    if (agentIds.length >= 3) {
      const firstAgent = agentIds[0]
      const branchAgents = agentIds.slice(1, -1)
      const lastAgent = agentIds[agentIds.length - 1]

      // First agent to decision node
      edges.push({
        id: `${firstAgent}-decision-1`,
        source: firstAgent,
        target: 'decision-1',
        type: 'smoothstep',
      })

      // Decision node to branch agents
      branchAgents.forEach((branchAgent, idx) => {
        edges.push({
          id: `decision-1-${branchAgent}`,
          source: 'decision-1',
          target: branchAgent,
          type: 'smoothstep',
          sourceHandle: idx === 0 ? 'true' : 'false',
          label: idx === 0 ? 'Yes' : 'No',
          labelStyle: {
            fill: idx === 0 ? '#22c55e' : '#ef4444',
            fontWeight: 600,
            fontSize: 11,
          },
          labelBgStyle: {
            fill: '#0f172a',
            fillOpacity: 0.9,
          },
        })
      })

      // Branch agents converge to last agent
      branchAgents.forEach((branchAgent) => {
        edges.push({
          id: `${branchAgent}-${lastAgent}`,
          source: branchAgent,
          target: lastAgent,
          type: 'smoothstep',
        })
      })

      // Last agent to End
      edges.push({
        id: `${lastAgent}-end`,
        source: lastAgent,
        target: 'end',
        type: 'smoothstep',
      })
    } else {
      // Fallback to sequential
      agentIds.forEach((agentId, idx) => {
        if (idx < agentIds.length - 1) {
          edges.push({
            id: `${agentId}-${agentIds[idx + 1]}`,
            source: agentId,
            target: agentIds[idx + 1],
            type: 'smoothstep',
          })
        }
      })
      edges.push({
        id: `${agentIds[agentIds.length - 1]}-end`,
        source: agentIds[agentIds.length - 1],
        target: 'end',
        type: 'smoothstep',
      })
    }
  } else {
    // Default to sequential for other patterns
    agentIds.forEach((agentId, idx) => {
      if (idx < agentIds.length - 1) {
        edges.push({
          id: `${agentId}-${agentIds[idx + 1]}`,
          source: agentId,
          target: agentIds[idx + 1],
          type: 'smoothstep',
        })
      }
    })
    edges.push({
      id: `${agentIds[agentIds.length - 1]}-end`,
      source: agentIds[agentIds.length - 1],
      target: 'end',
      type: 'smoothstep',
    })
  }

  return edges
}

/**
 * Get health-based color for node borders
 */
export function getHealthColor(score: number): string {
  if (score >= 0.9) return '#22c55e' // green-500
  if (score >= 0.8) return '#3b82f6' // blue-500
  if (score >= 0.6) return '#f59e0b' // amber-500
  return '#ef4444' // red-500
}
