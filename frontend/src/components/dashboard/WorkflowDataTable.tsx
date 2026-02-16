'use client'

import { useState, useMemo } from 'react'
import { ChevronUp, ChevronDown, ChevronsUpDown, Settings, Eye, EyeOff } from 'lucide-react'
import { QualityAssessment } from '@/lib/api'
import { QualityGradeBadge } from '@/components/quality/QualityGradeBadge'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'

type SortDirection = 'asc' | 'desc' | null
type SortConfig = { key: string; direction: SortDirection }

interface Column {
  key: string
  label: string
  sortable: boolean
  filterable: boolean
  defaultVisible: boolean
  width?: string
  render?: (value: any, row: QualityAssessment) => React.ReactNode
}

const COLUMNS: Column[] = [
  {
    key: 'workflow_name',
    label: 'Workflow Name',
    sortable: true,
    filterable: true,
    defaultVisible: true,
    width: '250px',
    render: (value) => (
      <div className="font-medium text-white truncate max-w-[230px]" title={value}>
        {value}
      </div>
    ),
  },
  {
    key: 'overall_grade',
    label: 'Grade',
    sortable: true,
    filterable: true,
    defaultVisible: true,
    width: '100px',
    render: (value) => <QualityGradeBadge grade={value} size="sm" />,
  },
  {
    key: 'overall_score',
    label: 'Score',
    sortable: true,
    filterable: true,
    defaultVisible: true,
    width: '100px',
    render: (value) => {
      // Value is already 0-100 from database
      const percent = Math.round(value)
      const color =
        percent >= 90 ? 'text-success-500' :
        percent >= 80 ? 'text-primary-500' :
        percent >= 70 ? 'text-accent-500' :
        'text-danger-500'
      return <span className={`font-mono font-medium ${color}`}>{percent}%</span>
    },
  },
  {
    key: 'critical_issues_count',
    label: 'Critical',
    sortable: true,
    filterable: true,
    defaultVisible: true,
    width: '100px',
    render: (value) => (
      value > 0 ? (
        <Badge variant="error">{value}</Badge>
      ) : (
        <span className="text-slate-500 text-sm">—</span>
      )
    ),
  },
  {
    key: 'total_issues',
    label: 'Issues',
    sortable: true,
    filterable: true,
    defaultVisible: true,
    width: '90px',
    render: (value) => (
      <span className="text-slate-300">{value}</span>
    ),
  },
  {
    key: 'pattern',
    label: 'Pattern',
    sortable: true,
    filterable: true,
    defaultVisible: true,
    width: '130px',
    render: (value, row) => {
      const pattern = row.orchestration_score?.detected_pattern || 'unknown'
      return (
        <span className="text-slate-300 text-sm capitalize">
          {pattern.replace(/-/g, ' ')}
        </span>
      )
    },
  },
  {
    key: 'agent_count',
    label: 'Agents',
    sortable: true,
    filterable: false,
    defaultVisible: true,
    width: '90px',
    render: (value, row) => (
      <span className="text-slate-300">{row.agent_scores.length}</span>
    ),
  },
  {
    key: 'created_at',
    label: 'Last Assessed',
    sortable: true,
    filterable: true,
    defaultVisible: true,
    width: '140px',
    render: (value) => {
      const date = new Date(value)
      const now = new Date()
      const diffMs = now.getTime() - date.getTime()
      const diffMins = Math.floor(diffMs / 60000)

      if (diffMins < 1) return 'Just now'
      if (diffMins < 60) return `${diffMins}m ago`
      if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`
      if (diffMins < 10080) return `${Math.floor(diffMins / 1440)}d ago`
      return date.toLocaleDateString()
    },
  },
  // Hidden by default columns
  {
    key: 'workflow_id',
    label: 'Workflow ID',
    sortable: true,
    filterable: true,
    defaultVisible: false,
    width: '160px',
    render: (value) => (
      <span className="font-mono text-xs text-slate-400" title={value}>
        {value.slice(0, 8)}...
      </span>
    ),
  },
  {
    key: 'agent_quality_score',
    label: 'Agent Score',
    sortable: true,
    filterable: true,
    defaultVisible: false,
    width: '120px',
    render: (value) => (
      <span className="font-mono text-slate-300">{Math.round(value * 100)}%</span>
    ),
  },
  {
    key: 'orchestration_quality_score',
    label: 'Orch Score',
    sortable: true,
    filterable: true,
    defaultVisible: false,
    width: '120px',
    render: (value) => (
      <span className="font-mono text-slate-300">{Math.round(value * 100)}%</span>
    ),
  },
  {
    key: 'source',
    label: 'Source',
    sortable: true,
    filterable: true,
    defaultVisible: false,
    width: '100px',
    render: (value) => (
      <span className="text-slate-400 text-sm capitalize">{value}</span>
    ),
  },
]

export function WorkflowDataTable({
  workflows,
  onSelectWorkflow,
  selectedWorkflowId,
}: {
  workflows: QualityAssessment[]
  onSelectWorkflow: (id: string) => void
  selectedWorkflowId: string | null
}) {
  const [sortConfig, setSortConfig] = useState<SortConfig>({
    key: 'assessed_at',
    direction: 'desc',
  })
  const [visibleColumns, setVisibleColumns] = useState<Set<string>>(
    new Set(COLUMNS.filter(c => c.defaultVisible).map(c => c.key))
  )
  const [showColumnControl, setShowColumnControl] = useState(false)

  // Sorting logic
  const sortedData = useMemo(() => {
    if (!sortConfig.direction) return workflows

    return [...workflows].sort((a, b) => {
      const aVal = getNestedValue(a, sortConfig.key)
      const bVal = getNestedValue(b, sortConfig.key)

      if (aVal === bVal) return 0

      const comparison = aVal > bVal ? 1 : -1
      return sortConfig.direction === 'asc' ? comparison : -comparison
    })
  }, [workflows, sortConfig])

  const handleSort = (key: string) => {
    setSortConfig(prev => ({
      key,
      direction:
        prev.key === key
          ? prev.direction === 'asc'
            ? 'desc'
            : prev.direction === 'desc'
            ? null
            : 'asc'
          : 'asc',
    }))
  }

  const handleToggleColumn = (key: string) => {
    setVisibleColumns(prev => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
  }

  const handleShowAll = () => {
    setVisibleColumns(new Set(COLUMNS.map(c => c.key)))
  }

  const handleHideAll = () => {
    // Keep at least workflow_name visible
    setVisibleColumns(new Set(['workflow_name']))
  }

  const visibleCols = COLUMNS.filter(c => visibleColumns.has(c.key))

  return (
    <div className="space-y-3">
      {/* Column Visibility Control */}
      <div className="flex justify-end">
        <div className="relative">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setShowColumnControl(!showColumnControl)}
          >
            <Settings size={16} className="mr-2" />
            Columns
          </Button>

          {showColumnControl && (
            <>
              <div
                className="fixed inset-0 z-10"
                onClick={() => setShowColumnControl(false)}
              />
              <div className="absolute right-0 mt-2 w-64 bg-slate-800 border border-slate-700 rounded-lg shadow-xl z-20">
                <div className="p-3 border-b border-slate-700">
                  <div className="text-sm font-medium text-white mb-2">
                    Column Visibility
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleShowAll}
                    >
                      Show All
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleHideAll}
                    >
                      Reset
                    </Button>
                  </div>
                </div>
                <div className="max-h-96 overflow-y-auto">
                  {COLUMNS.map(column => (
                    <label
                      key={column.key}
                      className="flex items-center gap-2 px-3 py-2 hover:bg-slate-700/50 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={visibleColumns.has(column.key)}
                        onChange={() => handleToggleColumn(column.key)}
                        className="rounded border-slate-600 text-primary-500 focus:ring-primary-500"
                      />
                      <span className="text-sm text-slate-300 flex-1">{column.label}</span>
                      {visibleColumns.has(column.key) ? (
                        <Eye size={14} className="text-primary-500" />
                      ) : (
                        <EyeOff size={14} className="text-slate-500" />
                      )}
                    </label>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Data Table */}
      <div className="overflow-x-auto bg-slate-900 border border-slate-700 rounded-lg">
        <table className="w-full border-collapse">
          <thead className="bg-slate-800/50">
            <tr className="border-b border-slate-700">
              {visibleCols.map(column => (
                <th
                  key={column.key}
                  className="px-4 py-3 text-left text-sm font-medium text-slate-300"
                  style={{ width: column.width }}
                >
                  {column.sortable ? (
                    <button
                      onClick={() => handleSort(column.key)}
                      className="flex items-center gap-2 hover:text-white transition-colors"
                    >
                      {column.label}
                      {sortConfig.key === column.key ? (
                        sortConfig.direction === 'asc' ? (
                          <ChevronUp size={16} className="text-primary-500" />
                        ) : (
                          <ChevronDown size={16} className="text-primary-500" />
                        )
                      ) : (
                        <ChevronsUpDown size={16} className="opacity-30" />
                      )}
                    </button>
                  ) : (
                    column.label
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedData.length === 0 ? (
              <tr>
                <td colSpan={visibleCols.length} className="px-4 py-12 text-center text-slate-400">
                  No workflows found
                </td>
              </tr>
            ) : (
              sortedData.map(workflow => (
                <tr
                  key={workflow.id}
                  onClick={() => onSelectWorkflow(workflow.workflow_id)}
                  className={`
                    border-b border-slate-800 cursor-pointer transition-colors
                    hover:bg-slate-800/50
                    ${selectedWorkflowId === workflow.workflow_id ? 'bg-primary-500/10 border-primary-500/30' : ''}
                  `}
                >
                  {visibleCols.map(column => (
                    <td key={column.key} className="px-4 py-3 text-sm">
                      {column.render
                        ? column.render(getNestedValue(workflow, column.key), workflow)
                        : getNestedValue(workflow, column.key)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Summary Footer */}
      <div className="text-sm text-slate-400 px-1">
        Showing {sortedData.length} workflow{sortedData.length !== 1 ? 's' : ''}
        {sortConfig.key && sortConfig.direction && (
          <span className="ml-2">
            • Sorted by {COLUMNS.find(c => c.key === sortConfig.key)?.label}{' '}
            ({sortConfig.direction === 'asc' ? 'ascending' : 'descending'})
          </span>
        )}
      </div>
    </div>
  )
}

function getNestedValue(obj: any, path: string): any {
  // Handle nested paths and derived values
  if (path === 'pattern') {
    return obj.orchestration_score?.detected_pattern || 'unknown'
  }
  if (path === 'agent_count') {
    return obj.agent_scores.length
  }
  return obj[path]
}
