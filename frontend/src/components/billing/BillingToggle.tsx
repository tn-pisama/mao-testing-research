'use client'

import { Switch } from '@/components/ui/Switch'
import { cn } from '@/lib/utils'
import { motion, AnimatePresence } from 'framer-motion'

interface BillingToggleProps {
  isAnnual: boolean
  onToggle: (annual: boolean) => void
}

export function BillingToggle({ isAnnual, onToggle }: BillingToggleProps) {
  return (
    <div className="inline-flex items-center gap-3">
      <span
        className={cn(
          'text-sm font-medium transition-colors',
          !isAnnual ? 'text-white' : 'text-zinc-500'
        )}
      >
        Monthly
      </span>
      <Switch checked={isAnnual} onCheckedChange={onToggle} />
      <span
        className={cn(
          'text-sm font-medium transition-colors',
          isAnnual ? 'text-white' : 'text-zinc-500'
        )}
      >
        Annual
      </span>
      <AnimatePresence>
        {isAnnual && (
          <motion.span
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            transition={{ duration: 0.2 }}
            className="ml-1 px-2.5 py-0.5 text-xs font-semibold rounded-full bg-green-500/15 border border-green-500/30 text-green-400"
          >
            Save ~17%
          </motion.span>
        )}
      </AnimatePresence>
    </div>
  )
}
