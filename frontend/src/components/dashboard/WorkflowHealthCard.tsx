'use client'

import { GitBranch, CheckCircle, AlertCircle, Clock } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card'
import Link from 'next/link'
import type { Trace } from '@/lib/api'

interface WorkflowHealthCardProps {
  traces: Trace[]
  isLoading?: boolean
}

export function WorkflowHealthCard({ traces, isLoading }: WorkflowHealthCardProps) {
  if (isLoading) {
    return (
      <Card>
        <div className="h-40 animate-pulse bg-slate-700 rounded-lg" />
      </Card>
    )
  }

  // Derive workflow stats from traces (use unique session_ids as proxy for workflows)
  const workflowIds = new Set(traces.map(t => t.session_id))
  const totalWorkflows = workflowIds.size || traces.length
  const healthyCount = traces.filter(t => t.status === 'success' || t.status === 'completed').length
  const failedCount = traces.filter(t => t.status === 'error' || t.status === 'failed').length
  const runningCount = traces.filter(t => t.status === 'running' || t.status === 'pending').length

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <GitBranch className="h-5 w-5 text-blue-400" />
            Workflows Monitored
          </CardTitle>
          <Link
            href="/n8n"
            className="text-sm text-blue-400 hover:text-blue-300"
          >
            Manage
          </Link>
        </div>
      </CardHeader>
      <CardContent>
        <div className="text-4xl font-bold text-white mb-4">
          {totalWorkflows}
        </div>
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div className="flex items-center gap-2">
            <CheckCircle className="h-4 w-4 text-green-400" />
            <span className="text-slate-400">Healthy:</span>
            <span className="font-medium text-green-400">{healthyCount}</span>
          </div>
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 text-red-400" />
            <span className="text-slate-400">Issues:</span>
            <span className="font-medium text-red-400">{failedCount}</span>
          </div>
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-yellow-400" />
            <span className="text-slate-400">Running:</span>
            <span className="font-medium text-yellow-400">{runningCount}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
