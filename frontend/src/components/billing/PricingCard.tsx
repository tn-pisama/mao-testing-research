'use client'

import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/Button'
import { Check } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import type { PlanDisplayData } from './billing-data'

interface PricingCardProps {
  display: PlanDisplayData
  isAnnual: boolean
  isCurrent: boolean
  isPopular: boolean
  isPurchasable: boolean
  onSelect: () => void
  isLoading: boolean
}

export function PricingCard({
  display,
  isAnnual,
  isCurrent,
  isPopular,
  isPurchasable,
  onSelect,
  isLoading,
}: PricingCardProps) {
  const isEnterprise = display.slug === 'enterprise'
  const isFree = display.slug === 'free'

  const displayPrice =
    isEnterprise
      ? 'Custom'
      : isAnnual && display.annualMonthlyPrice != null
        ? `$${display.annualMonthlyPrice}`
        : `$${display.monthlyPrice}`

  const showStrikethrough =
    isAnnual &&
    !isEnterprise &&
    !isFree &&
    display.annualMonthlyPrice != null &&
    display.monthlyPrice != null

  // Popular card wrapper with gradient border
  const cardContent = (
    <div
      className={cn(
        'flex flex-col h-full p-6 relative overflow-hidden',
        isPopular
          ? 'bg-zinc-900 rounded-[11px]'
          : 'bg-zinc-900 rounded-xl',
        isCurrent && !isPopular && 'ring-2 ring-blue-500/30'
      )}
    >
      {/* Subtle glow for popular */}
      {isPopular && (
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-3/4 h-24 bg-blue-500/5 blur-2xl rounded-full pointer-events-none" />
      )}

      {/* Popular badge */}
      {isPopular && (
        <div className="absolute -top-px left-1/2 -translate-x-1/2">
          <span className="inline-block px-3 py-1 text-xs font-semibold rounded-b-lg bg-gradient-to-r from-blue-600 to-violet-600 text-white shadow-lg shadow-blue-500/20">
            Most Popular
          </span>
        </div>
      )}

      {/* Header */}
      <div className={cn('mb-6', isPopular && 'mt-4')}>
        <p className="text-sm font-medium text-zinc-400 mb-1">{display.tagline}</p>
        <h3 className="text-lg font-semibold text-white mb-3">{display.name}</h3>

        <div className="flex items-baseline gap-1">
          <AnimatePresence mode="wait">
            <motion.span
              key={displayPrice}
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 8 }}
              transition={{ duration: 0.2 }}
              className="text-4xl font-bold text-white"
            >
              {displayPrice}
            </motion.span>
          </AnimatePresence>
          {!isEnterprise && display.monthlyPrice !== 0 && (
            <span className="text-sm text-zinc-400">/mo</span>
          )}
          {isFree && (
            <span className="text-sm text-zinc-400">forever</span>
          )}
        </div>
        {showStrikethrough && (
          <p className="text-sm text-zinc-500 mt-1">
            <span className="line-through">${display.monthlyPrice}/mo</span>
            <span className="text-zinc-400 ml-1.5">billed annually</span>
          </p>
        )}
      </div>

      {/* Features */}
      <ul className="space-y-2.5 mb-8 flex-1">
        {display.features.map((feature) => (
          <li key={feature} className="flex items-start gap-2.5 text-sm text-zinc-300">
            <Check
              size={16}
              className={cn(
                'mt-0.5 flex-shrink-0',
                isPopular ? 'text-blue-400' : isFree ? 'text-zinc-500' : 'text-blue-400'
              )}
            />
            {feature}
          </li>
        ))}
      </ul>

      {/* CTA */}
      <div className="mt-auto">
        {isCurrent ? (
          <Button variant="secondary" className="w-full" disabled>
            Current Plan
          </Button>
        ) : isEnterprise ? (
          <Button
            variant="secondary"
            className="w-full"
            onClick={() =>
              window.location.href =
                'mailto:team@pisama.ai?subject=Enterprise%20Plan%20Inquiry'
            }
          >
            Contact Sales
          </Button>
        ) : isFree ? (
          <Button variant="ghost" className="w-full" disabled>
            Free Tier
          </Button>
        ) : isPurchasable ? (
          <Button
            variant={isPopular ? 'primary' : 'secondary'}
            className="w-full"
            onClick={onSelect}
            isLoading={isLoading}
          >
            Upgrade to {display.name}
          </Button>
        ) : (
          <Button variant="ghost" className="w-full" disabled>
            Coming Soon
          </Button>
        )}
      </div>
    </div>
  )

  // Popular card gets gradient border wrapper
  if (isPopular) {
    return (
      <div className={cn('rounded-xl bg-gradient-to-b from-blue-500 to-violet-500 p-px lg:-translate-y-2', isCurrent && 'ring-2 ring-blue-500/30')}>
        {cardContent}
      </div>
    )
  }

  return (
    <div
      className={cn(
        'rounded-xl border transition-colors duration-300',
        isCurrent
          ? 'border-blue-500'
          : 'border-zinc-800 hover:border-zinc-700'
      )}
    >
      {cardContent}
    </div>
  )
}
