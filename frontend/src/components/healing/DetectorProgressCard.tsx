'use client'

import { cn } from '@/lib/utils'
import { Card, CardContent } from '../ui/Card'
import { CheckCircle2, Clock, XCircle, ArrowDown, Minus } from 'lucide-react'

interface DetectorProgress {
  before: number | null
  after: number | null
  status: 'pending' | 'fixing' | 'fixed' | 'failed' | 'rolled_back'
}

interface DetectorProgressCardProps {
  progress: Record<string, DetectorProgress>
}

const STATUS_CONFIG = {
  pending: { icon: Clock, color: 'text-zinc-400', bg: 'bg-zinc-500/20', label: 'Pending' },
  fixing: { icon: Clock, color: 'text-amber-400', bg: 'bg-amber-500/20', label: 'Fixing' },
  fixed: { icon: CheckCircle2, color: 'text-green-400', bg: 'bg-green-500/20', label: 'Fixed' },
  failed: { icon: XCircle, color: 'text-red-400', bg: 'bg-red-500/20', label: 'Failed' },
  rolled_back: { icon: ArrowDown, color: 'text-zinc-400', bg: 'bg-zinc-500/20', label: 'Rolled Back' },
}

function ConfidenceBar({ value, label }: { value: number | null; label: string }) {
  const pct = value != null ? Math.round(value * 100) : 0
  const color =
    pct === 0 ? 'bg-green-500' :
    pct < 30 ? 'bg-blue-500' :
    pct < 70 ? 'bg-amber-500' :
    'bg-red-500'

  return (
    <div className="flex items-center gap-2 min-w-0">
      <span className="text-[10px] text-zinc-500 w-8 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div className={cn('h-full rounded-full transition-all', color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[10px] font-mono text-zinc-400 w-8 text-right shrink-0">
        {value != null ? `${pct}%` : '—'}
      </span>
    </div>
  )
}

export function DetectorProgressCard({ progress }: DetectorProgressCardProps) {
  const entries = Object.entries(progress)
  if (entries.length === 0) return null

  const fixed = entries.filter(([, p]) => p.status === 'fixed').length
  const total = entries.length

  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-zinc-200">Detector Healing Progress</h3>
          <span className="text-xs text-zinc-500">
            {fixed}/{total} fixed
          </span>
        </div>

        <div className="space-y-2">
          {entries.map(([detector, prog]) => {
            const config = STATUS_CONFIG[prog.status] || STATUS_CONFIG.pending
            const Icon = config.icon
            const drop = prog.before != null && prog.after != null
              ? Math.round((1 - prog.after / Math.max(prog.before, 0.01)) * 100)
              : null

            return (
              <div key={detector} className="flex items-center gap-2">
                <Icon className={cn('w-3.5 h-3.5 shrink-0', config.color)} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-0.5">
                    <span className="text-xs text-zinc-300 truncate">{detector}</span>
                    <div className="flex items-center gap-1.5">
                      {drop != null && (
                        <span className={cn(
                          'text-[10px] font-mono',
                          drop >= 50 ? 'text-green-400' : drop > 0 ? 'text-amber-400' : 'text-zinc-500'
                        )}>
                          {drop > 0 ? `↓${drop}%` : drop === 0 ? '—' : `↑${Math.abs(drop)}%`}
                        </span>
                      )}
                      <span className={cn('text-[10px] px-1.5 py-0.5 rounded', config.bg, config.color)}>
                        {config.label}
                      </span>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <ConfidenceBar value={prog.before} label="Pre" />
                    <ConfidenceBar value={prog.after} label="Post" />
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
