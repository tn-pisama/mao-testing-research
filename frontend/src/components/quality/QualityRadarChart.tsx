'use client'

import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import {
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, Legend, ResponsiveContainer
} from 'recharts'
import type { AgentQualityScore } from '@/lib/api'

const AGENT_COLORS = ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#22c55e']

export function QualityRadarChart({ agentScores }: { agentScores: AgentQualityScore[] }) {
  const radarData = agentScores[0]?.dimensions.map((dim, i) => {
    const point: Record<string, string | number> = { dimension: dim.dimension.replace(/_/g, ' ') }
    agentScores.forEach(agent => {
      point[agent.agent_name] = Math.round((agent.dimensions[i]?.score || 0) * 100)
    })
    return point
  }) || []

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle>Agent Dimension Comparison</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={350}>
          <RadarChart data={radarData}>
            <PolarGrid stroke="#334155" />
            <PolarAngleAxis
              dataKey="dimension"
              tick={{ fill: '#94a3b8', fontSize: 12 }}
            />
            <PolarRadiusAxis
              angle={90}
              domain={[0, 100]}
              tick={{ fill: '#64748b', fontSize: 10 }}
            />
            {agentScores.map((agent, i) => (
              <Radar
                key={agent.agent_id}
                name={agent.agent_name}
                dataKey={agent.agent_name}
                stroke={AGENT_COLORS[i % AGENT_COLORS.length]}
                fill={AGENT_COLORS[i % AGENT_COLORS.length]}
                fillOpacity={0.15}
              />
            ))}
            <Legend
              wrapperStyle={{ color: '#94a3b8', fontSize: 12 }}
            />
          </RadarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}
