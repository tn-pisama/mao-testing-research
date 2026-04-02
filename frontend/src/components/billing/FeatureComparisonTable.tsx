'use client'

import { useState } from 'react'
import { cn } from '@/lib/utils'
import { Check, Minus, ChevronDown } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { comparisonCategories } from './billing-data'
import type { ComparisonRow } from './billing-data'

const PLAN_COLUMNS = ['free', 'pro', 'team', 'enterprise'] as const
const PLAN_LABELS: Record<string, string> = {
  free: 'Free',
  pro: 'Pro',
  team: 'Team',
  enterprise: 'Enterprise',
}

function CellValue({ value }: { value: string | boolean }) {
  if (typeof value === 'boolean') {
    return value ? (
      <Check size={16} className="text-green-400 mx-auto" />
    ) : (
      <Minus size={16} className="text-zinc-600 mx-auto" />
    )
  }
  return <span className="text-zinc-300 text-sm">{value}</span>
}

function ComparisonRow({ row }: { row: ComparisonRow }) {
  return (
    <div className="grid grid-cols-5 border-b border-zinc-800/50 hover:bg-zinc-900/40 transition-colors">
      <div className="px-4 py-3 text-sm text-zinc-300">{row.feature}</div>
      {PLAN_COLUMNS.map((plan) => (
        <div
          key={plan}
          className={cn(
            'px-4 py-3 text-center flex items-center justify-center',
            plan === 'pro' && 'bg-blue-500/[0.03]'
          )}
        >
          <CellValue value={row[plan]} />
        </div>
      ))}
    </div>
  )
}

export function FeatureComparisonTable() {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="mt-12">
      <button
        onClick={() => setExpanded(!expanded)}
        className="mx-auto flex items-center gap-2 text-sm font-medium text-zinc-400 hover:text-white transition-colors"
      >
        Compare all features
        <ChevronDown
          className={cn(
            'w-4 h-4 transition-transform duration-300',
            expanded && 'rotate-180'
          )}
        />
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="mt-6 rounded-xl border border-zinc-800 overflow-hidden">
              {/* Scrollable on mobile */}
              <div className="overflow-x-auto">
                <div className="min-w-[640px]">
                  {/* Header */}
                  <div className="grid grid-cols-5 bg-zinc-900/80 border-b border-zinc-800">
                    <div className="px-4 py-3 text-sm font-semibold text-zinc-400">
                      Feature
                    </div>
                    {PLAN_COLUMNS.map((plan) => (
                      <div
                        key={plan}
                        className={cn(
                          'px-4 py-3 text-sm font-semibold text-white text-center',
                          plan === 'pro' && 'bg-blue-500/[0.03]'
                        )}
                      >
                        {PLAN_LABELS[plan]}
                      </div>
                    ))}
                  </div>

                  {/* Categories & rows */}
                  {comparisonCategories.map((category) => (
                    <div key={category.name}>
                      <div className="px-4 py-2.5 text-xs font-semibold uppercase tracking-wider text-zinc-500 bg-zinc-950/50 border-b border-zinc-800/50">
                        {category.name}
                      </div>
                      {category.rows.map((row) => (
                        <ComparisonRow key={row.feature} row={row} />
                      ))}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
