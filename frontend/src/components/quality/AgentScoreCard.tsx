'use client'

import { useState } from 'react'
import { Bot, AlertCircle } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/Card'
import { QualityGradeBadge, getScoreColor } from '@/components/quality/QualityGradeBadge'
import { DimensionBar } from '@/components/quality/DimensionBar'
import type { AgentQualityScore } from '@/lib/api'

export function AgentScoreCard({ agent }: { agent: AgentQualityScore }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <Card className="mb-4">
      <CardContent className="p-4">
        <div
          className="flex items-center justify-between cursor-pointer"
          onClick={() => setExpanded(!expanded)}
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-500/20 rounded-lg">
              <Bot size={18} className="text-blue-400" />
            </div>
            <div>
              <h4 className="text-white font-medium">{agent.agent_name}</h4>
              <p className="text-sm text-zinc-500">{agent.agent_type}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className={`text-lg font-bold ${getScoreColor(agent.overall_score)}`}>
                {Math.round(agent.overall_score * 100)}%
              </div>
              <div className="text-xs text-zinc-500">{agent.issues_count} issues</div>
            </div>
            <QualityGradeBadge grade={agent.grade} size="md" />
          </div>
        </div>

        {expanded && (
          <div className="mt-4 pt-4 border-t border-zinc-700">
            <h5 className="text-sm font-medium text-zinc-300 mb-3">Dimension Scores</h5>
            {agent.dimensions.map((dim, i) => (
              <DimensionBar key={i} dimension={dim} />
            ))}

            {agent.critical_issues.length > 0 && (
              <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                <div className="flex items-center gap-2 text-red-400 mb-2">
                  <AlertCircle size={14} />
                  <span className="text-sm font-medium">Critical Issues</span>
                </div>
                <ul className="text-sm text-red-400/80 space-y-1">
                  {agent.critical_issues.map((issue, i) => (
                    <li key={i}>{issue}</li>
                  ))}
                </ul>
              </div>
            )}

            {agent.reasoning && (
              <div className="mt-4 p-3 bg-zinc-800 rounded-lg">
                <h5 className="text-xs font-medium text-zinc-500 uppercase mb-2">Reasoning</h5>
                <p className="text-sm text-zinc-300 leading-relaxed whitespace-pre-wrap">
                  {agent.reasoning}
                </p>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
