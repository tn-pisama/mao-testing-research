'use client'

import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Skeleton } from '@/components/ui/Skeleton'
import type { ChainAnalysisResponse, ChainAnalysisIssue } from '@/lib/api/traces'

const severityColors: Record<string, string> = {
  severe: 'bg-red-500/10 border-red-500/30 text-red-400',
  moderate: 'bg-amber-500/10 border-amber-500/30 text-amber-400',
  minor: 'bg-blue-500/10 border-blue-500/30 text-blue-400',
}

const issueTypeIcons: Record<string, string> = {
  cascade_failure: '\u26A1',
  data_corruption_propagation: '\u26D4',
  cross_chain_loop: '\u21BB',
  redundant_work: '\u2702',
}

function IssueCard({ issue }: { issue: ChainAnalysisIssue }) {
  const colors = severityColors[issue.severity] || severityColors.moderate
  const icon = issueTypeIcons[issue.issue_type] || '\u26A0'
  return (
    <div className={`rounded-xl border p-4 ${colors}`}>
      <div className="flex items-start gap-3">
        <span className="text-lg">{icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-semibold">{issue.issue_type.replace(/_/g, ' ')}</span>
            <span className="text-xs opacity-70 uppercase">{issue.severity}</span>
          </div>
          <p className="text-sm opacity-90">{issue.description}</p>
          {issue.affected_traces.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {issue.affected_traces.map(tid => (
                <span key={tid} className="text-xs font-mono opacity-60">{tid.slice(0, 8)}</span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export function ChainAnalysisPanel({ traceId }: { traceId: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['trace', traceId, 'chain-analysis'],
    queryFn: () => api.getChainAnalysis(traceId),
    enabled: !!traceId,
    retry: false,
  })

  if (isLoading) return <Skeleton className="h-48 rounded-xl" />
  if (error || !data) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6 text-center text-zinc-500">
        Chain analysis not available — no linked traces found
      </div>
    )
  }

  const r = data as ChainAnalysisResponse

  if (!r.detected && r.issues.length === 0) {
    return (
      <div className="rounded-xl border border-green-500/20 bg-green-500/5 p-6">
        <div className="flex items-center gap-3">
          <span className="text-2xl text-green-400">&#x2714;</span>
          <div>
            <h3 className="text-lg font-semibold text-green-400">No Cross-Chain Issues</h3>
            <p className="text-sm text-zinc-400 mt-1">
              Analyzed {r.trace_count} linked traces. {r.explanation}
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-white">Chain Analysis</h3>
          <p className="text-sm text-zinc-400 mt-1">
            {r.trace_count} linked traces analyzed
            {r.root_traces.length > 0 && (
              <> / Root: <span className="font-mono text-zinc-300">{r.root_traces[0]?.slice(0, 8)}</span></>
            )}
          </p>
        </div>
        {r.detected && (
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-red-500/10 border border-red-500/30">
            <span className="text-sm font-semibold text-red-400">
              {r.issues.length} issue{r.issues.length !== 1 ? 's' : ''} found
            </span>
            <span className="text-xs text-red-400/70">conf: {Math.round(r.confidence * 100)}%</span>
          </div>
        )}
      </div>

      {/* Issues */}
      <div className="space-y-3">
        {r.issues.map((issue, i) => (
          <IssueCard key={i} issue={issue} />
        ))}
      </div>

      {/* Explanation */}
      {r.explanation && (
        <p className="text-sm text-zinc-500 italic">{r.explanation}</p>
      )}
    </div>
  )
}
