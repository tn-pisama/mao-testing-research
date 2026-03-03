'use client'

import { useState } from 'react'
import {
  Clock,
  RotateCcw,
  CheckCircle2,
  XCircle,
  Upload,
  GitBranch,
  Loader2,
  ExternalLink,
  Copy
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { toast } from 'sonner'
import type { WorkflowVersion } from '@/lib/api'

interface VersionHistoryProps {
  versions: WorkflowVersion[]
  workflowId: string
  onRestore: (versionId: string) => Promise<void>
  isLoading?: boolean
}

const changeTypeConfig = {
  fix_applied: {
    label: 'Fix Applied',
    icon: Upload,
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/20',
    badgeVariant: 'info' as const
  },
  staged: {
    label: 'Staged',
    icon: Clock,
    color: 'text-amber-400',
    bgColor: 'bg-amber-500/20',
    badgeVariant: 'warning' as const
  },
  promoted: {
    label: 'Promoted',
    icon: CheckCircle2,
    color: 'text-green-400',
    bgColor: 'bg-green-500/20',
    badgeVariant: 'success' as const
  },
  rejected: {
    label: 'Rejected',
    icon: XCircle,
    color: 'text-red-400',
    bgColor: 'bg-red-500/20',
    badgeVariant: 'error' as const
  },
  rollback: {
    label: 'Rollback',
    icon: RotateCcw,
    color: 'text-zinc-400',
    bgColor: 'bg-zinc-500/20',
    badgeVariant: 'default' as const
  },
  restored: {
    label: 'Restored',
    icon: GitBranch,
    color: 'text-purple-400',
    bgColor: 'bg-purple-500/20',
    badgeVariant: 'info' as const
  }
}

function formatDate(isoString: string): string {
  const date = new Date(isoString)
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

export function VersionHistory({
  versions,
  workflowId,
  onRestore,
  isLoading = false
}: VersionHistoryProps) {
  const [restoringId, setRestoringId] = useState<string | null>(null)

  const handleRestore = async (versionId: string) => {
    setRestoringId(versionId)
    try {
      await onRestore(versionId)
    } finally {
      setRestoringId(null)
    }
  }

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Version History</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="animate-pulse">
                <div className="flex items-start gap-4">
                  <div className="w-8 h-8 bg-zinc-700 rounded-full" />
                  <div className="flex-1">
                    <div className="h-4 bg-zinc-700 rounded w-1/4 mb-2" />
                    <div className="h-3 bg-zinc-700 rounded w-1/2" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Version History</CardTitle>
          <span className="text-xs text-zinc-500">
            Workflow: {workflowId}
          </span>
        </div>
      </CardHeader>
      <CardContent>
        {versions.length === 0 ? (
          <div className="text-center py-8 text-zinc-400">
            <GitBranch size={24} className="mx-auto mb-2 opacity-50" />
            <p className="text-sm">No version history</p>
            <p className="text-xs text-zinc-500 mt-1">
              Versions are created when fixes are applied
            </p>
          </div>
        ) : (
          <div className="relative">
            {/* Timeline line */}
            <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-zinc-700" />

            {/* Version items */}
            <div className="space-y-4">
              {versions.map((version, idx) => {
                const config = changeTypeConfig[version.change_type] || changeTypeConfig.fix_applied
                const Icon = config.icon
                const isLatest = idx === 0

                return (
                  <div key={version.id} className="relative flex items-start gap-4 ml-0">
                    {/* Timeline dot */}
                    <div
                      className={`relative z-10 flex items-center justify-center w-8 h-8 rounded-full ${config.bgColor}`}
                    >
                      <Icon size={16} className={config.color} />
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0 pb-4">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-sm font-medium text-white">
                              Version {version.version_number}
                            </span>
                            <Badge variant={config.badgeVariant} size="sm">
                              {config.label}
                            </Badge>
                            {isLatest && (
                              <Badge variant="success" size="sm">
                                Current
                              </Badge>
                            )}
                          </div>
                          <p className="text-xs text-zinc-400 mb-2">
                            {formatDate(version.created_at)}
                          </p>
                          {version.change_description && (
                            <p className="text-sm text-zinc-300 mb-2">
                              {version.change_description}
                            </p>
                          )}
                          {version.healing_id && (
                            <button
                              onClick={() => {
                                navigator.clipboard.writeText(version.healing_id!)
                                toast.info('Healing ID copied', { description: version.healing_id })
                              }}
                              className="inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"
                            >
                              <Copy size={12} />
                              Healing: {version.healing_id.slice(0, 8)}...
                            </button>
                          )}
                        </div>

                        {/* Restore button (not for latest version) */}
                        {!isLatest && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleRestore(version.id)}
                            isLoading={restoringId === version.id}
                            leftIcon={restoringId === version.id
                              ? <Loader2 className="animate-spin" size={14} />
                              : <RotateCcw size={14} />
                            }
                            disabled={restoringId !== null}
                          >
                            Restore
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
