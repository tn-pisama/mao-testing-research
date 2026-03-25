'use client'

import { cn } from '@/lib/utils'

interface QualityScoreBadgeProps {
  score: number
  dimensions?: {
    correctness: number
    completeness: number
    safety: number
    efficiency: number
  }
  size?: 'sm' | 'md' | 'lg'
  showDimensions?: boolean
}

function getScoreColor(score: number): string {
  if (score >= 0.9) return 'text-green-400'
  if (score >= 0.7) return 'text-blue-400'
  if (score >= 0.5) return 'text-amber-400'
  return 'text-red-400'
}

function getScoreBg(score: number): string {
  if (score >= 0.9) return 'bg-green-500/10 border-green-500/20'
  if (score >= 0.7) return 'bg-blue-500/10 border-blue-500/20'
  if (score >= 0.5) return 'bg-amber-500/10 border-amber-500/20'
  return 'bg-red-500/10 border-red-500/20'
}

function getScoreLabel(score: number): string {
  if (score >= 0.9) return 'Excellent'
  if (score >= 0.7) return 'Good'
  if (score >= 0.5) return 'Fair'
  if (score >= 0.3) return 'Poor'
  return 'Critical'
}

const DIM_LABELS: Record<string, string> = {
  correctness: 'Correctness',
  completeness: 'Completeness',
  safety: 'Safety',
  efficiency: 'Efficiency',
}

const DIM_ICONS: Record<string, string> = {
  correctness: 'C',
  completeness: 'P',
  safety: 'S',
  efficiency: 'E',
}

export function QualityScoreBadge({
  score,
  dimensions,
  size = 'md',
  showDimensions = false,
}: QualityScoreBadgeProps) {
  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5',
    md: 'text-sm px-3 py-1',
    lg: 'text-base px-4 py-2',
  }

  return (
    <div className="inline-flex flex-col gap-1">
      <div
        className={cn(
          'inline-flex items-center gap-1.5 rounded-full border font-medium',
          getScoreBg(score),
          getScoreColor(score),
          sizeClasses[size]
        )}
      >
        <span className="font-mono">{(score * 100).toFixed(0)}%</span>
        <span className="text-zinc-500">|</span>
        <span>{getScoreLabel(score)}</span>
      </div>

      {showDimensions && dimensions && (
        <div className="flex gap-1">
          {Object.entries(dimensions).map(([dim, val]) => (
            <div
              key={dim}
              className={cn(
                'inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-mono border',
                getScoreBg(val),
                getScoreColor(val)
              )}
              title={`${DIM_LABELS[dim]}: ${(val * 100).toFixed(0)}%`}
            >
              <span className="font-bold">{DIM_ICONS[dim]}</span>
              <span>{(val * 100).toFixed(0)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
