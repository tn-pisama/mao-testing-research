'use client'

import { Link2, ArrowRight, AlertTriangle, CheckCircle2 } from 'lucide-react'
import { clsx } from 'clsx'

interface EvidenceItem {
  step: number
  title: string
  description: string
  spanId?: string
  isError?: boolean
  data?: Record<string, any>
}

interface EvidenceChainProps {
  items: EvidenceItem[]
  className?: string
}

export function EvidenceChain({ items, className }: EvidenceChainProps) {
  if (items.length === 0) {
    return null
  }

  return (
    <div className={clsx('bg-slate-800/50 rounded-xl border border-slate-700 p-4', className)}>
      <div className="flex items-center gap-2 mb-4">
        <Link2 className="w-5 h-5 text-primary-400" />
        <h3 className="font-semibold text-white">Evidence Chain</h3>
        <span className="px-2 py-0.5 text-xs bg-slate-700 text-slate-400 rounded-full">
          {items.length} steps
        </span>
      </div>

      <div className="relative">
        {/* Vertical line connecting steps */}
        <div className="absolute left-4 top-6 bottom-6 w-0.5 bg-slate-700" />

        <div className="space-y-4">
          {items.map((item, index) => (
            <div key={index} className="relative flex gap-4">
              {/* Step indicator */}
              <div
                className={clsx(
                  'relative z-10 flex items-center justify-center w-8 h-8 rounded-full border-2',
                  item.isError
                    ? 'bg-red-500/20 border-red-500/50'
                    : 'bg-slate-800 border-slate-600'
                )}
              >
                {item.isError ? (
                  <AlertTriangle className="w-4 h-4 text-red-400" />
                ) : (
                  <span className="text-xs font-medium text-slate-300">{item.step}</span>
                )}
              </div>

              {/* Content */}
              <div className="flex-1 pb-4">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium text-white text-sm">{item.title}</span>
                  {item.spanId && (
                    <span className="px-1.5 py-0.5 text-[10px] bg-slate-700 text-slate-400 rounded font-mono">
                      {item.spanId}
                    </span>
                  )}
                </div>
                <p className="text-sm text-slate-400">{item.description}</p>

                {item.data && Object.keys(item.data).length > 0 && (
                  <pre className="mt-2 text-xs text-slate-500 bg-slate-900/50 p-2 rounded overflow-x-auto">
                    {JSON.stringify(item.data, null, 2)}
                  </pre>
                )}
              </div>

              {/* Arrow to next step */}
              {index < items.length - 1 && (
                <ArrowRight className="absolute left-4 bottom-0 w-4 h-4 text-slate-600 transform translate-x-[-50%] translate-y-2 hidden" />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// Helper to convert detection evidence to EvidenceChain items
export function evidenceToChainItems(
  evidence: Record<string, any>[],
  affectedSpans: string[]
): EvidenceItem[] {
  const items: EvidenceItem[] = []

  evidence.forEach((ev, i) => {
    items.push({
      step: i + 1,
      title: ev.title || `Evidence ${i + 1}`,
      description: ev.description || JSON.stringify(ev),
      spanId: affectedSpans[i],
      isError: ev.is_error || ev.isError,
      data: ev.details || ev.data,
    })
  })

  return items
}
