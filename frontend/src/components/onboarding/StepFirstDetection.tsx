'use client'

import { useState, useEffect } from 'react'
import { CheckCircle2, Loader2, ShieldCheck, ArrowRight } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import type { createApiClient } from '@/lib/api'

interface Detection {
  id: string
  detection_type: string
  confidence: number
  description: string | null
}

interface StepFirstDetectionProps {
  apiClient: ReturnType<typeof createApiClient>
  traceId: string
  onComplete: () => void
}

export function StepFirstDetection({ apiClient, traceId, onComplete }: StepFirstDetectionProps) {
  const [loading, setLoading] = useState(true)
  const [detections, setDetections] = useState<Detection[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function runDetection() {
      try {
        const result = await apiClient.runOnboardingDetection(traceId)
        setDetections(result.detections)
      } catch (e) {
        setError((e as Error).message || 'Failed to run detection')
      } finally {
        setLoading(false)
      }
    }
    runDetection()
  }, [apiClient, traceId])

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-zinc-100">Running Detection</h2>
          <p className="text-zinc-400 mt-2">Analyzing your trace with 21 failure mode detectors...</p>
        </div>
        <Card className="border-zinc-800 bg-zinc-900">
          <CardContent className="p-8 flex flex-col items-center gap-4">
            <Loader2 className="w-12 h-12 text-blue-400 animate-spin" />
            <p className="text-zinc-400">This usually takes a few seconds</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-zinc-100">Detection Error</h2>
          <p className="text-red-400 mt-2">{error}</p>
        </div>
        <Button onClick={onComplete} className="w-full">
          Go to Dashboard
          <ArrowRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    )
  }

  const hasDetections = detections.length > 0

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-2xl font-bold text-zinc-100">
          {hasDetections ? 'Issues Detected' : 'Trace Looks Healthy!'}
        </h2>
        <p className="text-zinc-400 mt-2">
          {hasDetections
            ? `Found ${detections.length} potential issue${detections.length > 1 ? 's' : ''} in your trace`
            : 'No failures detected. Your agent is running well!'}
        </p>
      </div>

      {hasDetections ? (
        <div className="space-y-3">
          {detections.map((d) => (
            <Card key={d.id} className="border-zinc-800 bg-zinc-900">
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge
                        variant={d.confidence > 0.8 ? 'error' : d.confidence > 0.5 ? 'warning' : 'info'}
                      >
                        {d.detection_type}
                      </Badge>
                      <span className="text-xs text-zinc-500">
                        {Math.round(d.confidence * 100)}% confidence
                      </span>
                    </div>
                    {d.description && (
                      <p className="text-sm text-zinc-400 mt-1">{d.description}</p>
                    )}
                  </div>
                  <div className="w-20">
                    <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          d.confidence > 0.8
                            ? 'bg-red-500'
                            : d.confidence > 0.5
                            ? 'bg-amber-500'
                            : 'bg-blue-500'
                        }`}
                        style={{ width: `${d.confidence * 100}%` }}
                      />
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card className="border-zinc-800 bg-zinc-900">
          <CardContent className="p-8 flex flex-col items-center gap-4">
            <ShieldCheck className="w-16 h-16 text-green-500" />
            <p className="text-zinc-300">
              Try our demo scenarios to see how PISAMA detects failures like loops,
              hallucinations, and state corruption.
            </p>
          </CardContent>
        </Card>
      )}

      <Button onClick={onComplete} className="w-full">
        <CheckCircle2 className="w-4 h-4 mr-2" />
        Go to Dashboard
      </Button>
    </div>
  )
}
