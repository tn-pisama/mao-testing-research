'use client'

import { AlertCircle, TrendingUp, TrendingDown, ChevronRight } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card'
import Link from 'next/link'
import type { Detection } from '@/lib/api'

interface ProblemsOverviewCardProps {
  detections: Detection[]
  isLoading?: boolean
}

function getSeverity(details?: { severity?: string }): 'critical' | 'high' | 'medium' | 'low' {
  const severity = details?.severity
  if (severity === 'critical' || severity === 'high' || severity === 'medium' || severity === 'low') {
    return severity
  }
  return 'medium'
}

export function ProblemsOverviewCard({ detections, isLoading }: ProblemsOverviewCardProps) {
  if (isLoading) {
    return (
      <Card>
        <div className="h-40 animate-pulse bg-slate-700 rounded-lg" />
      </Card>
    )
  }

  const totalProblems = detections.length
  const criticalCount = detections.filter(d => getSeverity(d.details as { severity?: string }) === 'critical').length
  const highCount = detections.filter(d => getSeverity(d.details as { severity?: string }) === 'high').length

  // Simulate trend (in real app, compare to previous period)
  const trend = totalProblems > 5 ? 'up' : 'down'
  const trendPercent = totalProblems > 5 ? 12 : 8

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-amber-400" />
            Problems Found
          </CardTitle>
          <Link
            href="/detections"
            className="flex items-center gap-1 text-sm text-blue-400 hover:text-blue-300"
          >
            View all
            <ChevronRight size={16} />
          </Link>
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex items-end gap-3 mb-4">
          <div className="text-4xl font-bold text-white">
            {totalProblems}
          </div>
          <div className={`flex items-center gap-1 text-sm ${trend === 'down' ? 'text-green-400' : 'text-red-400'}`}>
            {trend === 'down' ? <TrendingDown size={16} /> : <TrendingUp size={16} />}
            {trendPercent}% this week
          </div>
        </div>

        {(criticalCount > 0 || highCount > 0) && (
          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
            <div className="text-sm text-red-400">
              {criticalCount > 0 && (
                <span className="font-medium">{criticalCount} critical</span>
              )}
              {criticalCount > 0 && highCount > 0 && ', '}
              {highCount > 0 && (
                <span className="font-medium">{highCount} high priority</span>
              )}
              {' '}need attention
            </div>
          </div>
        )}

        {criticalCount === 0 && highCount === 0 && totalProblems > 0 && (
          <div className="text-sm text-slate-400">
            All issues are low or medium priority
          </div>
        )}

        {totalProblems === 0 && (
          <div className="text-sm text-green-400">
            No problems detected - your workflows are healthy!
          </div>
        )}
      </CardContent>
    </Card>
  )
}
