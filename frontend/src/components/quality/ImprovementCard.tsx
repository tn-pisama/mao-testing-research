'use client'

import { useState } from 'react'
import { AlertCircle, AlertTriangle, Info, Clock } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import type { QualityImprovement } from '@/lib/api'

const severityConfig = {
  critical: { icon: AlertCircle, color: 'text-red-400', bg: 'bg-red-500/20', label: 'Critical' },
  high: { icon: AlertTriangle, color: 'text-orange-400', bg: 'bg-orange-500/20', label: 'High' },
  medium: { icon: AlertTriangle, color: 'text-amber-400', bg: 'bg-amber-500/20', label: 'Medium' },
  low: { icon: Info, color: 'text-zinc-400', bg: 'bg-zinc-500/20', label: 'Low' },
  info: { icon: Info, color: 'text-blue-400', bg: 'bg-blue-500/20', label: 'Info' },
}

const effortColors = {
  low: 'text-green-400',
  medium: 'text-amber-400',
  high: 'text-red-400',
}

export function ImprovementCard({ improvement }: { improvement: QualityImprovement }) {
  const [expanded, setExpanded] = useState(false)
  const config = severityConfig[improvement.severity] || severityConfig.info
  const Icon = config.icon

  return (
    <Card className="mb-3">
      <CardContent className="p-4">
        <div
          className="flex items-start gap-3 cursor-pointer"
          onClick={() => setExpanded(!expanded)}
        >
          <div className={`p-2 rounded-lg ${config.bg}`}>
            <Icon size={16} className={config.color} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h4 className="text-white font-medium">{improvement.title}</h4>
              <Badge
                variant={
                  improvement.severity === 'critical' ? 'error' :
                  improvement.severity === 'high' ? 'warning' : 'default'
                }
              >
                {improvement.severity}
              </Badge>
            </div>
            <p className="text-sm text-zinc-400">{improvement.description}</p>

            <div className="flex items-center gap-4 mt-2">
              <span className="text-xs text-zinc-500">{improvement.category}</span>
              <span className="text-xs text-zinc-500">
                {improvement.target_type}: {improvement.target_id}
              </span>
              <span className={`text-xs flex items-center gap-1 ${effortColors[improvement.effort]}`}>
                <Clock size={10} />
                {improvement.effort} effort
              </span>
            </div>
          </div>
        </div>

        {expanded && (
          <div className="mt-4 pt-4 border-t border-zinc-700 space-y-3">
            {improvement.rationale && (
              <div>
                <h5 className="text-xs font-medium text-zinc-500 uppercase mb-1">Rationale</h5>
                <p className="text-sm text-zinc-300">{improvement.rationale}</p>
              </div>
            )}
            {improvement.suggested_change && (
              <div>
                <h5 className="text-xs font-medium text-zinc-500 uppercase mb-1">Suggested Change</h5>
                <p className="text-sm text-zinc-300">{improvement.suggested_change}</p>
              </div>
            )}
            {improvement.code_example && (
              <div>
                <h5 className="text-xs font-medium text-zinc-500 uppercase mb-1">Code Example</h5>
                <pre className="text-sm text-zinc-400 bg-zinc-900 p-3 rounded-lg overflow-x-auto">
                  {improvement.code_example}
                </pre>
              </div>
            )}
            {improvement.estimated_impact && (
              <div>
                <h5 className="text-xs font-medium text-zinc-500 uppercase mb-1">Estimated Impact</h5>
                <p className="text-sm text-green-400">{improvement.estimated_impact}</p>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
