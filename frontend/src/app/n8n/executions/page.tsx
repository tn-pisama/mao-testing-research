'use client'

export const dynamic = 'force-dynamic'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import { useExecutionStream, ExecutionEvent } from '@/hooks/useExecutionStream'
import {
  Play,
  CheckCircle,
  XCircle,
  Clock,
  Filter,
  RefreshCw,
  ExternalLink,
  Loader2,
  AlertCircle,
  Search,
  Activity
} from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { createApiClient } from '@/lib/api'

interface ExecutionDisplay {
  id: string
  executionId: string
  workflowName: string
  status: 'success' | 'error' | 'running' | 'unknown'
  startedAt: Date
  completedAt?: Date
  duration?: number
  tokenCount: number
}

export default function ExecutionsPage() {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const router = useRouter()

  const [executions, setExecutions] = useState<ExecutionDisplay[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [showFilters, setShowFilters] = useState(false)

  const loadExecutions = useCallback(async () => {
    setIsLoading(true)
    setError(null)

    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)

      // Fetch all traces (we'll filter client-side for n8n)
      const response = await api.getTraces({ page: 1, perPage: 100 })

      // Filter for n8n traces only
      const n8nTraces = response.traces.filter(trace => trace.framework === 'n8n')

      const executionsData: ExecutionDisplay[] = n8nTraces.map(trace => {
        const startedAt = new Date(trace.created_at)
        const completedAt = trace.completed_at ? new Date(trace.completed_at) : undefined
        const duration = completedAt ? completedAt.getTime() - startedAt.getTime() : undefined

        return {
          id: trace.id,
          executionId: trace.session_id,
          workflowName: `Workflow ${trace.session_id.substring(0, 8)}`,
          status: trace.status === 'completed' ? 'success' : trace.status === 'error' ? 'error' : 'unknown',
          startedAt,
          completedAt,
          duration,
          tokenCount: trace.total_tokens || 0,
        }
      })

      setExecutions(executionsData)
    } catch (err) {
      console.error('Failed to load executions:', err)
      setError('Failed to load execution logs')
    } finally {
      setIsLoading(false)
    }
  }, [getToken, tenantId])

  useEffect(() => {
    loadExecutions()
  }, [loadExecutions])

  // Handle real-time execution events
  const handleExecutionEvent = useCallback((event: ExecutionEvent) => {
    console.log('Received execution event:', event)

    const newExecution: ExecutionDisplay = {
      id: event.trace_id,
      executionId: event.execution_id,
      workflowName: event.workflow_name,
      status: event.status === 'success' ? 'success' : event.status === 'error' ? 'error' : 'unknown',
      startedAt: event.started_at ? new Date(event.started_at) : new Date(),
      completedAt: event.finished_at ? new Date(event.finished_at) : undefined,
      duration: event.started_at && event.finished_at
        ? new Date(event.finished_at).getTime() - new Date(event.started_at).getTime()
        : undefined,
      tokenCount: 0, // Will be updated by backend
    }

    setExecutions(prev => {
      // Check if execution already exists (update case)
      const existingIndex = prev.findIndex(e => e.id === newExecution.id)
      if (existingIndex >= 0) {
        const updated = [...prev]
        updated[existingIndex] = newExecution
        return updated
      }

      // New execution - prepend to list
      return [newExecution, ...prev]
    })
  }, [])

  // Connect to real-time execution stream
  const { isConnected } = useExecutionStream({
    onExecution: handleExecutionEvent,
    enabled: true,
  })

  // Apply filters
  const filteredExecutions = executions.filter(execution => {
    if (statusFilter !== 'all' && execution.status !== statusFilter) {
      return false
    }
    if (searchQuery && !execution.workflowName.toLowerCase().includes(searchQuery.toLowerCase()) &&
      !execution.executionId.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false
    }
    return true
  })

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success':
        return <CheckCircle size={16} className="text-emerald-400" />
      case 'error':
        return <XCircle size={16} className="text-red-400" />
      case 'running':
        return <Play size={16} className="text-blue-400" />
      default:
        return <AlertCircle size={16} className="text-zinc-400" />
    }
  }

  const getStatusBadge = (status: string) => {
    const variants: Record<string, 'success' | 'error' | 'default'> = {
      success: 'success',
      error: 'error',
      running: 'default',
    }
    return (
      <Badge variant={variants[status] || 'default'} size="sm">
        {status}
      </Badge>
    )
  }

  const formatDuration = (ms?: number) => {
    if (!ms) return 'N/A'
    const seconds = Math.floor(ms / 1000)
    if (seconds < 60) return `${seconds}s`
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = seconds % 60
    return `${minutes}m ${remainingSeconds}s`
  }

  return (
    <Layout>
      <div className="p-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-orange-600/20 rounded-lg">
                <Play className="w-6 h-6 text-orange-400" />
              </div>
              <h1 className="text-2xl font-bold text-white">Workflow Executions</h1>
              {isConnected && (
                <div className="flex items-center gap-2 px-2 py-1 bg-emerald-500/20 rounded-lg border border-emerald-500/30">
                  <Activity size={14} className="text-emerald-400 animate-pulse" />
                  <span className="text-xs font-medium text-emerald-400">Live</span>
                </div>
              )}
            </div>
            <p className="text-zinc-400">
              View and analyze your n8n workflow execution history
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              onClick={() => setShowFilters(!showFilters)}
              leftIcon={<Filter size={16} />}
            >
              Filters
            </Button>
            <Button
              variant="secondary"
              onClick={loadExecutions}
              leftIcon={<RefreshCw size={16} />}
            >
              Refresh
            </Button>
          </div>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-3">
            <AlertCircle size={20} className="text-red-400" />
            <p className="text-sm text-red-300">{error}</p>
          </div>
        )}

        {/* Filters */}
        {showFilters && (
          <div className="mb-6 p-4 bg-zinc-800 rounded-xl border border-zinc-700 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm text-zinc-400 mb-2 block">Status</label>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="w-full px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-lg text-white text-sm focus:outline-none focus:border-orange-500"
                >
                  <option value="all">All</option>
                  <option value="success">Success</option>
                  <option value="error">Error</option>
                  <option value="running">Running</option>
                </select>
              </div>
              <div>
                <label className="text-sm text-zinc-400 mb-2 block">Search</label>
                <div className="relative">
                  <Search size={16} className="absolute left-3 top-1/2 transform -translate-y-1/2 text-zinc-500" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search by workflow name or execution ID..."
                    className="w-full pl-10 pr-3 py-2 bg-zinc-900 border border-zinc-700 rounded-lg text-white text-sm focus:outline-none focus:border-orange-500"
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700">
            <div className="text-2xl font-bold text-white">{executions.length}</div>
            <div className="text-sm text-zinc-400">Total Executions</div>
          </div>
          <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700">
            <div className="text-2xl font-bold text-emerald-400">
              {executions.filter(e => e.status === 'success').length}
            </div>
            <div className="text-sm text-zinc-400">Successful</div>
          </div>
          <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700">
            <div className="text-2xl font-bold text-red-400">
              {executions.filter(e => e.status === 'error').length}
            </div>
            <div className="text-sm text-zinc-400">Failed</div>
          </div>
          <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700">
            <div className="text-2xl font-bold text-blue-400">
              {executions.filter(e => e.status === 'running').length}
            </div>
            <div className="text-sm text-zinc-400">Running</div>
          </div>
        </div>

        {/* Execution List */}
        <div className="bg-zinc-800 rounded-xl border border-zinc-700">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-orange-400 animate-spin" />
            </div>
          ) : filteredExecutions.length === 0 ? (
            <div className="text-center py-12 px-4">
              <Play className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
              <p className="text-zinc-400 mb-2">
                {searchQuery || statusFilter !== 'all'
                  ? 'No executions match your filters'
                  : 'No executions found'}
              </p>
              <p className="text-zinc-500 text-sm">
                {searchQuery || statusFilter !== 'all'
                  ? 'Try adjusting your filters'
                  : 'Execute a workflow to see it here'}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="border-b border-zinc-700">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">
                      Workflow
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">
                      Execution ID
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">
                      Started At
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">
                      Duration
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">
                      Tokens
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-zinc-400 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-700">
                  {filteredExecutions.map((execution) => (
                    <tr
                      key={execution.id}
                      className="hover:bg-zinc-700/50 transition-colors cursor-pointer"
                      onClick={() => router.push(`/traces/${execution.id}`)}
                    >
                      <td className="px-4 py-4 whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          {getStatusIcon(execution.status)}
                          {getStatusBadge(execution.status)}
                        </div>
                      </td>
                      <td className="px-4 py-4">
                        <div className="text-sm font-medium text-white">
                          {execution.workflowName}
                        </div>
                      </td>
                      <td className="px-4 py-4">
                        <code className="text-xs text-zinc-400 bg-zinc-900 px-2 py-1 rounded">
                          {execution.executionId.substring(0, 12)}...
                        </code>
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap">
                        <div className="text-sm text-zinc-300">
                          {execution.startedAt.toLocaleString()}
                        </div>
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap">
                        <div className="flex items-center gap-1 text-sm text-zinc-300">
                          <Clock size={12} className="text-zinc-500" />
                          {formatDuration(execution.duration)}
                        </div>
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap">
                        <div className="text-sm text-zinc-300">
                          {execution.tokenCount.toLocaleString()}
                        </div>
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation()
                            router.push(`/traces/${execution.id}`)
                          }}
                          leftIcon={<ExternalLink size={14} />}
                        >
                          View Details
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Help Text */}
        <div className="mt-6 p-4 bg-zinc-800/50 rounded-xl border border-zinc-700">
          <p className="text-sm text-zinc-400">
            <strong className="text-white">Tip:</strong> Click on any execution to see detailed
            trace information, including node execution order, data flow, and any detected issues.
          </p>
        </div>
      </div>
    </Layout>
  )
}
