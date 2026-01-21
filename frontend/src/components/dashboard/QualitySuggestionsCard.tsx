'use client'

import { Lightbulb, ChevronRight, AlertCircle, AlertTriangle, Info, Clock } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card'
import { Badge } from '../ui/Badge'
import Link from 'next/link'
import type { QualityImprovement } from '@/lib/api'

interface QualitySuggestionsCardProps {
  suggestions?: QualityImprovement[]
  isLoading?: boolean
  maxItems?: number
}

const severityConfig = {
  critical: { icon: AlertCircle, color: 'text-red-400', bg: 'bg-red-500/20', label: 'Critical' },
  high: { icon: AlertTriangle, color: 'text-orange-400', bg: 'bg-orange-500/20', label: 'High' },
  medium: { icon: AlertTriangle, color: 'text-amber-400', bg: 'bg-amber-500/20', label: 'Medium' },
  low: { icon: Info, color: 'text-slate-400', bg: 'bg-slate-500/20', label: 'Low' },
  info: { icon: Info, color: 'text-blue-400', bg: 'bg-blue-500/20', label: 'Info' },
}

const effortColors = {
  low: 'text-green-400',
  medium: 'text-amber-400',
  high: 'text-red-400',
}

export function QualitySuggestionsCard({
  suggestions = [],
  isLoading,
  maxItems = 5,
}: QualitySuggestionsCardProps) {
  if (isLoading) {
    return (
      <Card>
        <div className="h-64 animate-pulse bg-slate-700 rounded-lg" />
      </Card>
    )
  }

  // Sort by severity (critical first) and take top items
  const sortedSuggestions = [...suggestions]
    .sort((a, b) => {
      const order = { critical: 0, high: 1, medium: 2, low: 3, info: 4 }
      return (order[a.severity] ?? 5) - (order[b.severity] ?? 5)
    })
    .slice(0, maxItems)

  const criticalCount = suggestions.filter(s => s.severity === 'critical').length
  const highCount = suggestions.filter(s => s.severity === 'high').length

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Lightbulb className="h-5 w-5 text-amber-400" />
            Improvement Suggestions
          </CardTitle>
          <Link
            href="/quality"
            className="flex items-center gap-1 text-sm text-blue-400 hover:text-blue-300"
          >
            View all
            <ChevronRight size={16} />
          </Link>
        </div>
      </CardHeader>
      <CardContent>
        {suggestions.length === 0 ? (
          <div className="text-center py-6">
            <div className="text-green-400 mb-2">All workflows are optimized!</div>
            <div className="text-sm text-slate-400">
              No improvement suggestions at this time
            </div>
          </div>
        ) : (
          <>
            {(criticalCount > 0 || highCount > 0) && (
              <div className="flex items-center gap-2 mb-4 text-sm">
                {criticalCount > 0 && (
                  <Badge variant="error">{criticalCount} critical</Badge>
                )}
                {highCount > 0 && (
                  <Badge variant="warning">{highCount} high</Badge>
                )}
              </div>
            )}

            <div className="space-y-3">
              {sortedSuggestions.map((suggestion) => {
                const config = severityConfig[suggestion.severity] || severityConfig.info
                const Icon = config.icon

                return (
                  <div
                    key={suggestion.id}
                    className="p-3 bg-slate-800/50 rounded-lg border border-slate-700 hover:border-slate-600 transition-colors"
                  >
                    <div className="flex items-start gap-3">
                      <div className={`p-1.5 rounded ${config.bg}`}>
                        <Icon size={14} className={config.color} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-medium text-white text-sm truncate">
                            {suggestion.title}
                          </span>
                        </div>
                        <div className="text-xs text-slate-400 line-clamp-2">
                          {suggestion.description}
                        </div>
                        <div className="flex items-center gap-3 mt-2">
                          <span className="text-xs text-slate-500">
                            {suggestion.category}
                          </span>
                          <span className="text-xs text-slate-500">•</span>
                          <span className={`text-xs flex items-center gap-1 ${effortColors[suggestion.effort]}`}>
                            <Clock size={10} />
                            {suggestion.effort} effort
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>

            {suggestions.length > maxItems && (
              <div className="mt-3 text-center">
                <Link
                  href="/quality"
                  className="text-sm text-blue-400 hover:text-blue-300"
                >
                  +{suggestions.length - maxItems} more suggestions
                </Link>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
