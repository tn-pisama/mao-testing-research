'use client'

export const dynamic = 'force-dynamic'

import { useState, useEffect, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import {
  Heart, ArrowLeft, Loader2, AlertTriangle, Check, X, RotateCcw,
  Clock, ChevronDown, ChevronUp, Code2, Shield
} from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { QualityHealingStatusBadge } from '@/components/quality/QualityHealingStatusBadge'
import { CodeDiffViewer } from '@/components/healing/CodeDiffViewer'
import { HealingTimeline } from '@/components/healing/HealingTimeline'
import { createApiClient, QualityHealingRecord } from '@/lib/api'
import Link from 'next/link'

export default function QualityHealingDetailPage() {
  const params = useParams()
  const router = useRouter()
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const [healing, setHealing] = useState<QualityHealingRecord | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedFix, setExpandedFix] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  const healingId = params?.id as string

  const loadHealing = useCallback(async () => {
    if (!healingId) return
    setIsLoading(true)
    setError(null)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      const result = await api.getQualityHealing(healingId)
      setHealing(result)
    } catch (err) {
      console.warn('Failed to load healing:', err)
      setError('Failed to load healing record.')
    }
    setIsLoading(false)
  }, [getToken, tenantId, healingId])

  useEffect(() => {
    loadHealing()
  }, [loadHealing])

  const handleApprove = async (fixId?: string) => {
    if (!healing) return
    setActionLoading('approve')
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      await api.approveQualityHealing(healing.id, {
        approved: true,
        fix_ids: fixId ? [fixId] : undefined,
      })
      await loadHealing()
    } catch (err) {
      console.warn('Failed to approve:', err)
    }
    setActionLoading(null)
  }

  const handleRollback = async () => {
    if (!healing) return
    setActionLoading('rollback')
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      await api.rollbackQualityHealing(healing.id)
      await loadHealing()
    } catch (err) {
      console.warn('Failed to rollback:', err)
    }
    setActionLoading(null)
  }

  if (isLoading) {
    return (
      <Layout>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-8 h-8 text-green-400 animate-spin" />
        </div>
      </Layout>
    )
  }

  if (error || !healing) {
    return (
      <Layout>
        <div className="p-6 max-w-4xl mx-auto">
          <div className="p-6 bg-red-500/10 border border-red-500/20 rounded-xl text-center">
            <AlertTriangle className="w-10 h-10 text-red-400 mx-auto mb-3" />
            <p className="text-red-300 mb-4">{error || 'Healing record not found'}</p>
            <Button variant="secondary" onClick={() => router.push('/quality/healing')}>
              Back to Healing List
            </Button>
          </div>
        </div>
      </Layout>
    )
  }

  const improvement = healing.after_score !== null
    ? Math.round(healing.after_score - healing.before_score)
    : null

  return (
    <Layout>
      <div className="p-6 max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-4 mb-6">
          <Link href="/quality/healing">
            <Button variant="ghost" size="sm">
              <ArrowLeft size={16} className="mr-2" />
              Back
            </Button>
          </Link>
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <Heart className="w-6 h-6 text-green-400" />
              <h1 className="text-xl font-bold text-white">Healing Detail</h1>
              <QualityHealingStatusBadge status={healing.status} size="md" />
            </div>
          </div>
          <div className="flex gap-2">
            {healing.status === 'pending' || healing.status === 'staged' ? (
              <Button
                onClick={() => handleApprove()}
                disabled={actionLoading === 'approve'}
              >
                {actionLoading === 'approve' ? (
                  <Loader2 size={16} className="animate-spin mr-2" />
                ) : (
                  <Check size={16} className="mr-2" />
                )}
                Approve All
              </Button>
            ) : null}
            {healing.rollback_available && (
              <Button
                variant="destructive"
                onClick={handleRollback}
                disabled={actionLoading === 'rollback'}
              >
                {actionLoading === 'rollback' ? (
                  <Loader2 size={16} className="animate-spin mr-2" />
                ) : (
                  <RotateCcw size={16} className="mr-2" />
                )}
                Rollback
              </Button>
            )}
          </div>
        </div>

        {/* Score Summary */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <Card>
            <CardContent className="p-4 text-center">
              <p className="text-sm text-zinc-400 mb-1">Before</p>
              <p className="text-3xl font-bold text-white">{Math.round(healing.before_score)}%</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 text-center">
              <p className="text-sm text-zinc-400 mb-1">After</p>
              <p className={`text-3xl font-bold ${
                healing.after_score !== null
                  ? healing.after_score > healing.before_score ? 'text-green-400' : 'text-red-400'
                  : 'text-zinc-500'
              }`}>
                {healing.after_score !== null ? `${Math.round(healing.after_score)}%` : '--'}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 text-center">
              <p className="text-sm text-zinc-400 mb-1">Improvement</p>
              <p className={`text-3xl font-bold ${
                improvement !== null && improvement > 0 ? 'text-green-400' : 'text-zinc-500'
              }`}>
                {improvement !== null ? `${improvement > 0 ? '+' : ''}${improvement}%` : '--'}
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Timeline */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-sm">Healing Timeline</CardTitle>
          </CardHeader>
          <CardContent>
            <HealingTimeline healing={healing} />
          </CardContent>
        </Card>

        {/* Dimensions Targeted */}
        {healing.dimensions_targeted.length > 0 && (
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-sm">Dimensions Targeted</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex gap-2 flex-wrap">
                {healing.dimensions_targeted.map((dim) => (
                  <Badge key={dim} variant="secondary" className="capitalize">
                    {dim.replace(/_/g, ' ')}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Fix Suggestions */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2">
              <Shield size={16} className="text-blue-400" />
              Fix Suggestions ({healing.fix_suggestions_count})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {healing.fix_suggestions && healing.fix_suggestions.length > 0 ? (
              healing.fix_suggestions.map((fix: any) => (
                <div
                  key={fix.id || fix.title}
                  className="border border-zinc-700 rounded-lg p-4"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <h4 className="text-white font-medium text-sm">{fix.title}</h4>
                      <Badge variant={
                        fix.confidence === 'high' ? 'default' :
                        fix.confidence === 'medium' ? 'secondary' : 'outline'
                      }>
                        {fix.confidence}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-2">
                      {healing.status === 'pending' || healing.status === 'staged' ? (
                        <Button size="sm" variant="secondary" onClick={() => handleApprove(fix.id)}>
                          Apply
                        </Button>
                      ) : null}
                      <button
                        onClick={() => setExpandedFix(expandedFix === fix.id ? null : fix.id)}
                        className="text-zinc-400 hover:text-white transition-colors"
                      >
                        {expandedFix === fix.id ? (
                          <ChevronUp size={16} />
                        ) : (
                          <ChevronDown size={16} />
                        )}
                      </button>
                    </div>
                  </div>
                  <p className="text-sm text-zinc-400 mb-2">{fix.description}</p>
                  {fix.tags && fix.tags.length > 0 && (
                    <div className="flex gap-1 mb-2">
                      {fix.tags.map((tag: string) => (
                        <span key={tag} className="px-1.5 py-0.5 text-xs bg-zinc-800 text-zinc-500 rounded">
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                  {expandedFix === fix.id && fix.code_changes && (
                    <div className="mt-3 space-y-3">
                      {fix.code_changes.map((change: any, idx: number) => (
                        <div key={idx}>
                          <div className="flex items-center gap-2 mb-2">
                            <Code2 size={14} className="text-zinc-400" />
                            <span className="text-xs text-zinc-400 font-mono">{change.file_path}</span>
                          </div>
                          <CodeDiffViewer
                            diff={change.diff || change.suggested_code || ''}
                            language={change.language || 'python'}
                          />
                        </div>
                      ))}
                      {fix.rationale && (
                        <div className="mt-3 p-3 bg-zinc-800/50 rounded-lg">
                          <p className="text-xs text-zinc-400 font-medium mb-1">Rationale</p>
                          <p className="text-sm text-zinc-300">{fix.rationale}</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))
            ) : (
              <p className="text-sm text-zinc-500 text-center py-4">No fix suggestions available</p>
            )}
          </CardContent>
        </Card>

        {/* Validation Results */}
        {healing.validation_results && healing.validation_results.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Validation Results</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {healing.validation_results.map((result: any, idx: number) => (
                <div key={idx} className="flex items-center gap-3 p-3 bg-zinc-800/50 rounded-lg">
                  {result.success ? (
                    <Check size={16} className="text-green-400" />
                  ) : (
                    <X size={16} className="text-red-400" />
                  )}
                  <span className="text-sm text-zinc-300 flex-1">
                    {result.validation_type || result.name || `Validation ${idx + 1}`}
                  </span>
                  {result.error_message && (
                    <span className="text-xs text-red-400">{result.error_message}</span>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>
    </Layout>
  )
}
