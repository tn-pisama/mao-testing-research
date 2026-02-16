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
  critical: { icon: AlertCircle, color: 'text-danger-500', bg: 'bg-danger-500/20', label: 'Critical' },
  high: { icon: AlertTriangle, color: 'text-accent-500', bg: 'bg-accent-500/20', label: 'High' },
  medium: { icon: AlertTriangle, color: 'text-accent-500', bg: 'bg-accent-500/20', label: 'Medium' },
  low: { icon: Info, color: 'text-white/60', bg: 'bg-white/10', label: 'Low' },
  info: { icon: Info, color: 'text-primary-500', bg: 'bg-primary-500/20', label: 'Info' },
}

const effortColors = {
  low: 'text-success-500',
  medium: 'text-accent-500',
  high: 'text-danger-500',
}

export function QualitySuggestionsCard({
  suggestions = [],
  isLoading,
  maxItems = 5,
}: QualitySuggestionsCardProps) {
  if (isLoading) {
    return (
      <Card>
        <div className="h-64 animate-pulse bg-primary-500/20 rounded-lg" />
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
            <Lightbulb className="h-5 w-5 text-accent-500" />
            Improvement Suggestions
          </CardTitle>
          <Link
            href="/quality"
            className="flex items-center gap-1 text-sm text-primary-500 hover:text-primary-400 font-mono"
          >
            View all
            <ChevronRight size={16} />
          </Link>
        </div>
      </CardHeader>
      <CardContent>
        {suggestions.length === 0 ? (
          <div className="text-center py-6">
            <div className="text-success-500 mb-2 font-mono">All workflows are optimized!</div>
            <div className="text-sm text-white/60 font-mono">
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
                    className="p-3 bg-primary-500/10 rounded-lg border border-primary-500/30 hover:border-primary-500/50 hover:shadow-glow-green transition-all"
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
                        <div className="text-xs text-white/60 font-mono line-clamp-2">
                          {suggestion.description}
                        </div>
                        <div className="flex items-center gap-3 mt-2">
                          <span className="text-xs text-white/40 font-mono">
                            {suggestion.category}
                          </span>
                          <span className="text-xs text-white/40">•</span>
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
                  className="text-sm text-primary-500 hover:text-primary-400 font-mono"
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
