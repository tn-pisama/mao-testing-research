'use client'

import { useEffect, useState } from 'react'
import { clsx } from 'clsx'
import { AlertTriangle, RotateCcw, Zap, AlertCircle, ChevronRight } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

type DetectionType = 'loop' | 'corruption' | 'deadlock' | 'healthy'

interface Detection {
  id: string
  type: DetectionType
  title: string
  description: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  confidence: number
  timestamp: Date
  affectedAgents: string[]
}

const severityConfig = {
  low: { color: 'text-blue-400', bgColor: 'bg-blue-500/20', borderColor: 'border-blue-500/30' },
  medium: { color: 'text-amber-400', bgColor: 'bg-amber-500/20', borderColor: 'border-amber-500/30' },
  high: { color: 'text-orange-400', bgColor: 'bg-orange-500/20', borderColor: 'border-orange-500/30' },
  critical: { color: 'text-red-400', bgColor: 'bg-red-500/20', borderColor: 'border-red-500/30' },
}

const typeConfig: Record<DetectionType, { icon: typeof AlertTriangle; label: string }> = {
  loop: { icon: RotateCcw, label: 'Infinite Loop' },
  corruption: { icon: Zap, label: 'State Corruption' },
  deadlock: { icon: AlertCircle, label: 'Deadlock' },
  healthy: { icon: AlertTriangle, label: 'Unknown' },
}

function generateDetection(type: DetectionType): Detection {
  const detections: Record<DetectionType, Omit<Detection, 'id' | 'timestamp'>> = {
    loop: {
      type: 'loop',
      title: 'Infinite Loop Detected',
      description: 'Agents cycling through same states repeatedly. Pattern: Research → Analyze → Research',
      severity: 'high',
      confidence: 0.94,
      affectedAgents: ['Researcher', 'Analyzer'],
    },
    corruption: {
      type: 'corruption',
      title: 'State Corruption Detected',
      description: 'Semantic drift in agent state. Goal vector diverging from original intent.',
      severity: 'critical',
      confidence: 0.87,
      affectedAgents: ['Writer', 'Validator'],
    },
    deadlock: {
      type: 'deadlock',
      title: 'Coordination Deadlock',
      description: 'Circular dependency: Planner waiting for Executor, Executor waiting for Planner.',
      severity: 'high',
      confidence: 0.91,
      affectedAgents: ['Planner', 'Executor', 'Coordinator'],
    },
    healthy: {
      type: 'healthy',
      title: 'System Healthy',
      description: 'All agents operating normally',
      severity: 'low',
      confidence: 1.0,
      affectedAgents: [],
    },
  }

  return {
    id: Math.random().toString(36).substring(2),
    timestamp: new Date(),
    ...detections[type],
  }
}

interface LiveDetectionFeedProps {
  scenario: DetectionType
  isActive: boolean
}

export function LiveDetectionFeed({ scenario, isActive }: LiveDetectionFeedProps) {
  const [detections, setDetections] = useState<Detection[]>([])
  const [expanded, setExpanded] = useState<string | null>(null)

  useEffect(() => {
    if (isActive && scenario !== 'healthy') {
      const detection = generateDetection(scenario)
      setDetections([detection])
      setExpanded(detection.id)
    }
  }, [scenario, isActive])

  if (detections.length === 0) return null

  return (
    <div className="bg-slate-800/50 rounded-xl border border-red-500/30 overflow-hidden animate-fade-in">
      <div className="px-4 py-3 border-b border-red-500/20 bg-red-500/10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle size={16} className="text-red-400" />
            <h3 className="font-semibold text-white text-sm">Live Detections</h3>
          </div>
          <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-red-500/20 text-red-400 animate-pulse">
            {detections.length} Active
          </span>
        </div>
      </div>

      <div className="divide-y divide-slate-700/50">
        {detections.map((detection) => {
          const typeInfo = typeConfig[detection.type]
          const severityInfo = severityConfig[detection.severity]
          const TypeIcon = typeInfo.icon
          const isExpanded = expanded === detection.id

          return (
            <div key={detection.id} className="p-4">
              <button
                onClick={() => setExpanded(isExpanded ? null : detection.id)}
                className="w-full text-left"
              >
                <div className="flex items-start gap-3">
                  <div className={clsx('p-2 rounded-lg', severityInfo.bgColor)}>
                    <TypeIcon size={16} className={severityInfo.color} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-white text-sm">{detection.title}</span>
                      <span className={clsx(
                        'px-1.5 py-0.5 text-[10px] font-medium rounded uppercase',
                        severityInfo.bgColor,
                        severityInfo.color
                      )}>
                        {detection.severity}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-slate-500">
                      <span>{(detection.confidence * 100).toFixed(0)}% confidence</span>
                      <span>{formatDistanceToNow(detection.timestamp, { addSuffix: true })}</span>
                    </div>
                  </div>
                  <ChevronRight
                    size={16}
                    className={clsx(
                      'text-slate-500 transition-transform',
                      isExpanded && 'rotate-90'
                    )}
                  />
                </div>
              </button>

              {isExpanded && (
                <div className="mt-3 pl-11 space-y-3 animate-fade-in">
                  <p className="text-sm text-slate-400">{detection.description}</p>
                  <div className="flex flex-wrap gap-2">
                    {detection.affectedAgents.map((agent) => (
                      <span
                        key={agent}
                        className="px-2 py-1 text-xs rounded bg-slate-700/50 text-slate-300"
                      >
                        {agent}
                      </span>
                    ))}
                  </div>
                  <div className="flex gap-2">
                    <button className="px-3 py-1.5 text-xs font-medium rounded-lg bg-primary-600 text-white hover:bg-primary-500 transition-colors">
                      View Details
                    </button>
                    <button className="px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-700 text-slate-300 hover:bg-slate-600 transition-colors">
                      Dismiss
                    </button>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
