'use client'

export const dynamic = 'force-dynamic'

import { useState, useEffect, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import { Layout } from '@/components/common/Layout'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { createApiClient, Detection } from '@/lib/api'
import Link from 'next/link'
import {
  ArrowLeft,
  AlertTriangle,
  AlertCircle,
  CheckCircle,
  XCircle,
  Clock,
  Activity,
  ThumbsUp,
  ThumbsDown,
  Wrench,
  ExternalLink,
  Loader2,
  Info,
  Zap,
} from 'lucide-react'
import clsx from 'clsx'

function getSeverityFromType(type: string): 'critical' | 'high' | 'medium' | 'low' {
  if (type.includes('infinite') || type.includes('deadlock')) return 'critical'
  if (type.includes('loop') || type.includes('corrupt')) return 'high'
  if (type.includes('drift') || type.includes('hallucination')) return 'medium'
  return 'low'
}

function SeverityBadge({ severity }: { severity: string }) {
  const colors = {
    critical: 'bg-red-500/20 text-red-400 border-red-500/30',
    high: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
    medium: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    low: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  }

  return (
    <span className={clsx(
      'px-2 py-1 text-xs font-medium rounded-full border',
      colors[severity as keyof typeof colors] || colors.medium
    )}>
      {severity.charAt(0).toUpperCase() + severity.slice(1)}
    </span>
  )
}

export default function DetectionDetailPage() {
  const params = useParams()
  const router = useRouter()
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const [detection, setDetection] = useState<Detection | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [validating, setValidating] = useState(false)
  const [triggeringHealing, setTriggeringHealing] = useState(false)
  const [healingTriggered, setHealingTriggered] = useState(false)
  const [healingError, setHealingError] = useState<string | null>(null)

  const detectionId = params.id as string

  const loadDetection = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      const data = await api.getDetection(detectionId)
      setDetection(data)
    } catch (err) {
      console.error('Failed to load detection:', err)
      setError('Failed to load detection details')
    }
    setIsLoading(false)
  }, [getToken, tenantId, detectionId])

  useEffect(() => {
    loadDetection()
  }, [loadDetection])

  const handleTriggerHealing = async () => {
    if (!detection) return
    setTriggeringHealing(true)
    setHealingError(null)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      await api.triggerHealing(detection.id, { approval_required: true })
      setHealingTriggered(true)
    } catch (err) {
      console.error('Failed to trigger healing:', err)
      setHealingError('Failed to trigger healing. Try again.')
    }
    setTriggeringHealing(false)
  }

  const handleValidate = async (isFalsePositive: boolean) => {
    if (!detection) return
    setValidating(true)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      await api.validateDetection(detection.id, { false_positive: isFalsePositive })
      setDetection(prev => prev ? {
        ...prev,
        validated: true,
        false_positive: isFalsePositive,
      } : null)
    } catch (err) {
      console.error('Failed to validate detection:', err)
    }
    setValidating(false)
  }

  if (isLoading) {
    return (
      <Layout>
        <div className="p-6 flex items-center justify-center min-h-[400px]">
          <Loader2 size={32} className="animate-spin text-slate-400" />
        </div>
      </Layout>
    )
  }

  if (error || !detection) {
    return (
      <Layout>
        <div className="p-6">
          <div className="flex items-center gap-4 mb-6">
            <button
              onClick={() => router.back()}
              className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
            >
              <ArrowLeft size={20} />
            </button>
            <h1 className="text-2xl font-bold text-white">Detection Not Found</h1>
          </div>
          <Card>
            <CardContent className="p-8 text-center">
              <AlertCircle size={48} className="mx-auto mb-4 text-slate-500" />
              <p className="text-slate-400 mb-4">{error || 'Detection not found'}</p>
              <Button onClick={() => router.push('/detections')}>
                Back to Detections
              </Button>
            </CardContent>
          </Card>
        </div>
      </Layout>
    )
  }

  const severity = getSeverityFromType(detection.detection_type)

  return (
    <Layout>
      <div className="p-6 max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-4 mb-6">
          <button
            onClick={() => router.back()}
            className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
          >
            <ArrowLeft size={20} />
          </button>
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-1">
              <AlertTriangle className="w-6 h-6 text-amber-400" />
              <h1 className="text-2xl font-bold text-white">Detection Details</h1>
              <SeverityBadge severity={severity} />
              {detection.validated && (
                detection.false_positive ? (
                  <Badge variant="default">False Positive</Badge>
                ) : (
                  <Badge variant="success">Validated</Badge>
                )
              )}
            </div>
            <p className="text-slate-400 text-sm">
              {detection.detection_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
            </p>
          </div>
        </div>

        {/* Main Content */}
        <div className="space-y-6">
          {/* Summary Card */}
          <Card>
            <CardHeader>
              <CardTitle>Summary</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-slate-500 mb-1">Detection Type</p>
                  <p className="text-sm text-white font-medium">
                    {detection.detection_type.replace(/_/g, ' ')}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-slate-500 mb-1">Confidence</p>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
                      <div
                        className={clsx(
                          'h-full rounded-full',
                          detection.confidence >= 80 ? 'bg-red-500' :
                          detection.confidence >= 60 ? 'bg-amber-500' : 'bg-blue-500'
                        )}
                        style={{ width: `${detection.confidence}%` }}
                      />
                    </div>
                    <span className="text-sm text-white font-medium">
                      {Math.round(detection.confidence)}%
                    </span>
                  </div>
                </div>
                <div>
                  <p className="text-xs text-slate-500 mb-1">Detection Method</p>
                  <p className="text-sm text-white">{detection.method}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500 mb-1">Detected At</p>
                  <p className="text-sm text-white flex items-center gap-1">
                    <Clock size={14} className="text-slate-400" />
                    {new Date(detection.created_at).toLocaleString()}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Explanation */}
          {detection.explanation && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Info size={18} className="text-blue-400" />
                  What Happened
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-slate-300">{detection.explanation}</p>
              </CardContent>
            </Card>
          )}

          {/* Business Impact */}
          {detection.business_impact && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Zap size={18} className="text-amber-400" />
                  Business Impact
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-slate-300">{detection.business_impact}</p>
              </CardContent>
            </Card>
          )}

          {/* Suggested Action */}
          {detection.suggested_action && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Wrench size={18} className="text-emerald-400" />
                  Suggested Action
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-slate-300 mb-4">{detection.suggested_action}</p>
                <Link href={`/healing?detection=${detection.id}`}>
                  <Button size="sm" leftIcon={<Wrench size={14} />}>
                    View Auto-Fix Suggestions
                  </Button>
                </Link>
              </CardContent>
            </Card>
          )}

          {/* Technical Details */}
          <Card>
            <CardHeader>
              <CardTitle>Technical Details</CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="text-xs text-slate-400 bg-slate-900 p-4 rounded-lg overflow-x-auto">
                {JSON.stringify(detection.details, null, 2)}
              </pre>
            </CardContent>
          </Card>

          {/* Healing triggered banner */}
          {healingTriggered && (
            <div className="p-4 bg-purple-500/10 border border-purple-500/20 rounded-xl flex items-center gap-3">
              <CheckCircle size={18} className="text-purple-400 flex-shrink-0" />
              <p className="text-sm text-purple-300 flex-1">
                Healing triggered — fix suggestions generated.
              </p>
              <Link href="/healing">
                <Button variant="ghost" size="sm" rightIcon={<ExternalLink size={14} />}>
                  View in Self-Healing
                </Button>
              </Link>
            </div>
          )}
          {healingError && (
            <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-3">
              <AlertTriangle size={18} className="text-red-400 flex-shrink-0" />
              <p className="text-sm text-red-300">{healingError}</p>
            </div>
          )}

          {/* Actions */}
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <Link href={`/traces/${detection.trace_id}`}>
                    <Button variant="secondary" leftIcon={<Activity size={16} />}>
                      View Trace
                    </Button>
                  </Link>
                  <Link href={`/healing?detection=${detection.id}`}>
                    <Button variant="secondary" leftIcon={<Wrench size={16} />}>
                      View Fixes
                    </Button>
                  </Link>
                  <Button
                    variant="primary"
                    leftIcon={triggeringHealing ? <Loader2 size={16} className="animate-spin" /> : <Zap size={16} />}
                    onClick={handleTriggerHealing}
                    disabled={triggeringHealing || healingTriggered || detection.false_positive === true}
                  >
                    {healingTriggered ? 'Healing Triggered' : 'Trigger Healing'}
                  </Button>
                </div>

                {!detection.validated && (
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-slate-400 mr-2">Was this helpful?</span>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => handleValidate(false)}
                      disabled={validating}
                      leftIcon={<ThumbsUp size={14} />}
                    >
                      Valid
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => handleValidate(true)}
                      disabled={validating}
                      leftIcon={<ThumbsDown size={14} />}
                    >
                      False Positive
                    </Button>
                  </div>
                )}

                {detection.validated && (
                  <div className="flex items-center gap-2 text-sm">
                    {detection.false_positive ? (
                      <>
                        <XCircle size={16} className="text-slate-400" />
                        <span className="text-slate-400">Marked as false positive</span>
                      </>
                    ) : (
                      <>
                        <CheckCircle size={16} className="text-emerald-400" />
                        <span className="text-emerald-400">Validated as correct</span>
                      </>
                    )}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </Layout>
  )
}
