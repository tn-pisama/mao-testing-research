'use client'

import { useState, useEffect, useRef } from 'react'
import { Card, CardContent } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { Radio, ShieldCheck } from 'lucide-react'
import type { DemoDetection } from '@/lib/demo-fixtures'

interface LiveDetectionFeedProps {
  detections: DemoDetection[]
  isActive: boolean
  scenario?: string
}

export function LiveDetectionFeed({ detections, isActive }: LiveDetectionFeedProps) {
  const [visibleCount, setVisibleCount] = useState(0)
  const timerRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset count when detections change
    setVisibleCount(0)
    if (timerRef.current) clearInterval(timerRef.current)

    if (isActive && detections.length > 0) {
      // Reveal detections one by one with a delay
      timerRef.current = setInterval(() => {
        setVisibleCount((prev) => {
          if (prev >= detections.length) {
            if (timerRef.current) clearInterval(timerRef.current)
            return prev
          }
          return prev + 1
        })
      }, 1500)
    }

    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [isActive, detections])

  const visibleDetections = detections.slice(0, visibleCount)

  if (detections.length === 0) {
    return (
      <Card className="border-zinc-800 bg-zinc-900">
        <CardContent className="p-6 flex flex-col items-center gap-3 text-center">
          <ShieldCheck size={32} className="text-green-500" />
          <p className="text-sm text-zinc-300 font-medium">All Clear</p>
          <p className="text-xs text-zinc-500">No failures detected in this scenario</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 mb-3">
        <Radio size={14} className={`${isActive ? 'text-red-400 animate-pulse' : 'text-zinc-500'}`} />
        <span className="text-xs font-medium text-zinc-400 uppercase tracking-wider">
          Detection Feed
        </span>
        {visibleCount < detections.length && isActive && (
          <span className="text-xs text-zinc-600">Analyzing...</span>
        )}
      </div>

      {visibleDetections.map((d, i) => (
        <Card
          key={d.id}
          className="border-zinc-800 bg-zinc-900 animate-in slide-in-from-right duration-300"
          style={{ animationDelay: `${i * 100}ms` }}
        >
          <CardContent className="p-3">
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <Badge
                    variant={
                      d.confidence > 0.8
                        ? 'error'
                        : d.confidence > 0.5
                        ? 'warning'
                        : 'info'
                    }
                    className="text-xs"
                  >
                    {d.detection_type}
                  </Badge>
                </div>
                {d.explanation && (
                  <p className="text-xs text-zinc-400 line-clamp-2">{d.explanation}</p>
                )}
              </div>
              <div className="text-right shrink-0">
                <span
                  className={`text-xs font-mono ${
                    d.confidence > 0.8
                      ? 'text-red-400'
                      : d.confidence > 0.5
                      ? 'text-amber-400'
                      : 'text-blue-400'
                  }`}
                >
                  {Math.round(d.confidence * 100)}%
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
