'use client'

import { Layout } from '@/components/common/Layout'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'
import { cn } from '@/lib/utils'
import {
  useBillingPlans,
  useBillingStatus,
  useCreateCheckout,
  useBillingPortal,
} from '@/hooks/useBilling'
import type { BillingPlan } from '@/hooks/useBilling'
import {
  CreditCard,
  AlertTriangle,
  Check,
  ExternalLink,
} from 'lucide-react'

// ---------------------------------------------------------------------------
// Status badge mapping
// ---------------------------------------------------------------------------

const statusBadge: Record<string, { variant: 'success' | 'warning' | 'error' | 'info' | 'default'; label: string }> = {
  active: { variant: 'success', label: 'Active' },
  trialing: { variant: 'info', label: 'Trial' },
  past_due: { variant: 'error', label: 'Past Due' },
  canceled: { variant: 'error', label: 'Canceled' },
  incomplete: { variant: 'warning', label: 'Incomplete' },
}

// ---------------------------------------------------------------------------
// Static plan display data (features shown in pricing table)
// ---------------------------------------------------------------------------

interface PlanDisplay {
  slug: string
  name: string
  price: string
  priceNote?: string
  features: string[]
}

const planDisplayData: PlanDisplay[] = [
  {
    slug: 'free',
    name: 'Free',
    price: '$0',
    priceNote: 'forever',
    features: [
      '1 project',
      '100 daily runs',
      'Core detectors',
      '7-day retention',
      'Community support',
    ],
  },
  {
    slug: 'pro',
    name: 'Pro',
    price: '$29',
    priceNote: '/mo',
    features: [
      '10 projects',
      '5,000 daily runs',
      'All detectors',
      '30-day retention',
      'Email support',
      'Webhooks',
    ],
  },
  {
    slug: 'team',
    name: 'Team',
    price: '$79',
    priceNote: '/mo',
    features: [
      '50 projects',
      '25,000 daily runs',
      'All detectors + ML tier',
      '90-day retention',
      'Priority support',
      'SSO & RBAC',
      'Custom webhooks',
    ],
  },
  {
    slug: 'enterprise',
    name: 'Enterprise',
    price: 'Custom',
    features: [
      'Unlimited projects',
      'Unlimited runs',
      'All detectors + ML + custom',
      '365-day retention',
      'Dedicated support',
      'SLA guarantee',
      'On-prem option',
      'Custom integrations',
    ],
  },
]

// ---------------------------------------------------------------------------
// Usage bar component
// ---------------------------------------------------------------------------

function UsageBar({ label, used, limit }: { label: string; used: number; limit: number }) {
  const pct = limit > 0 ? Math.min((used / limit) * 100, 100) : 0
  const isHigh = pct >= 80

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm text-zinc-400">{label}</span>
        <span className={cn('text-sm font-medium', isHigh ? 'text-amber-400' : 'text-zinc-100')}>
          {used.toLocaleString()} / {limit.toLocaleString()}
        </span>
      </div>
      <div className="h-2 rounded-full bg-zinc-800 overflow-hidden">
        <div
          className={cn(
            'h-full rounded-full transition-all duration-500',
            isHigh ? 'bg-amber-500' : 'bg-blue-500'
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Current plan status section
// ---------------------------------------------------------------------------

function CurrentPlanStatus() {
  const { status, isLoading } = useBillingStatus()
  const portal = useBillingPortal()

  const handleManage = async () => {
    const result = await portal.mutateAsync()
    if (result.portal_url) {
      window.location.href = result.portal_url
    }
  }

  if (isLoading) {
    return (
      <div className="p-6 rounded-xl bg-zinc-900/50 border border-zinc-800">
        <Skeleton className="h-6 w-48 mb-4" />
        <Skeleton className="h-4 w-32 mb-6" />
        <div className="space-y-4">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
        </div>
      </div>
    )
  }

  if (!status) {
    return (
      <div className="p-6 rounded-xl bg-zinc-900/50 border border-zinc-800">
        <p className="text-zinc-400 text-sm">Unable to load billing status.</p>
      </div>
    )
  }

  const badge = statusBadge[status.status] ?? { variant: 'default' as const, label: status.status }

  return (
    <div className="p-6 rounded-xl bg-zinc-900/50 border border-zinc-800">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-600/20 rounded-lg">
            <CreditCard className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-semibold text-white">{status.plan_name}</h3>
              <Badge variant={badge.variant} size="sm">{badge.label}</Badge>
            </div>
            <p className="text-sm text-zinc-400">
              Current period ends {new Date(status.current_period_end).toLocaleDateString()}
            </p>
          </div>
        </div>
        <Button
          variant="secondary"
          onClick={handleManage}
          isLoading={portal.isPending}
        >
          Manage Subscription
          <ExternalLink size={14} className="ml-2" />
        </Button>
      </div>

      {status.cancel_at_period_end && (
        <div className="flex items-center gap-2 p-3 mb-4 rounded-lg bg-amber-500/10 border border-amber-500/20">
          <AlertTriangle size={16} className="text-amber-400 flex-shrink-0" />
          <p className="text-sm text-amber-300">
            Your subscription will cancel at the end of the current period. You can reactivate from the billing portal.
          </p>
        </div>
      )}

      <div className="space-y-3">
        <UsageBar
          label="Projects"
          used={status.usage.projects_used}
          limit={status.usage.projects_limit}
        />
        <UsageBar
          label="Daily Runs"
          used={status.usage.daily_runs_used}
          limit={status.usage.daily_runs_limit}
        />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Pricing card component
// ---------------------------------------------------------------------------

function PricingCard({
  display,
  plan,
  isCurrent,
  onSelect,
  isLoading,
}: {
  display: PlanDisplay
  plan?: BillingPlan
  isCurrent: boolean
  onSelect: (plan: BillingPlan) => void
  isLoading: boolean
}) {
  const isEnterprise = display.slug === 'enterprise'
  const isFree = display.slug === 'free'

  return (
    <div
      className={cn(
        'flex flex-col rounded-xl bg-zinc-900 border p-6 transition-colors',
        isCurrent
          ? 'border-blue-500 ring-2 ring-blue-500/20'
          : 'border-zinc-800 hover:border-zinc-700'
      )}
    >
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-white mb-1">{display.name}</h3>
        <div className="flex items-baseline gap-1">
          <span className="text-3xl font-bold text-white">{display.price}</span>
          {display.priceNote && (
            <span className="text-sm text-zinc-400">{display.priceNote}</span>
          )}
        </div>
      </div>

      <ul className="space-y-2.5 mb-8 flex-1">
        {display.features.map((feature) => (
          <li key={feature} className="flex items-start gap-2 text-sm text-zinc-300">
            <Check size={16} className="text-blue-400 mt-0.5 flex-shrink-0" />
            {feature}
          </li>
        ))}
      </ul>

      <div className="mt-auto">
        {isCurrent ? (
          <Button variant="secondary" className="w-full" disabled>
            Current Plan
          </Button>
        ) : isEnterprise ? (
          <Button
            variant="secondary"
            className="w-full"
            onClick={() => window.location.href = 'mailto:team@pisama.ai?subject=Enterprise%20Plan%20Inquiry'}
          >
            Contact Us
          </Button>
        ) : isFree ? (
          <Button variant="ghost" className="w-full" disabled>
            Free Tier
          </Button>
        ) : plan?.stripe_price_id ? (
          <Button
            variant="primary"
            className="w-full"
            onClick={() => onSelect(plan)}
            isLoading={isLoading}
          >
            Upgrade to {display.name}
          </Button>
        ) : (
          <Button variant="ghost" className="w-full" disabled>
            Unavailable
          </Button>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Pricing table section
// ---------------------------------------------------------------------------

function PricingTable() {
  const { plans, isLoading: plansLoading } = useBillingPlans()
  const { status } = useBillingStatus()
  const checkout = useCreateCheckout()

  const handleSelect = async (plan: BillingPlan) => {
    if (!plan.stripe_price_id) return
    const result = await checkout.mutateAsync({ price_id: plan.stripe_price_id })
    if (result.checkout_url) {
      window.location.href = result.checkout_url
    }
  }

  if (plansLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="p-6 rounded-xl bg-zinc-900/50 border border-zinc-800">
            <Skeleton className="h-6 w-24 mb-2" />
            <Skeleton className="h-8 w-20 mb-6" />
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, j) => (
                <Skeleton key={j} className="h-4 w-full" />
              ))}
            </div>
            <Skeleton className="h-10 w-full mt-8" />
          </div>
        ))}
      </div>
    )
  }

  const currentSlug = status?.plan_id ?? 'free'

  // Map API plans by slug for lookup
  const planBySlug = new Map<string, BillingPlan>()
  for (const p of plans) {
    planBySlug.set(p.slug, p)
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {planDisplayData.map((display) => (
        <PricingCard
          key={display.slug}
          display={display}
          plan={planBySlug.get(display.slug)}
          isCurrent={currentSlug === display.slug}
          onSelect={handleSelect}
          isLoading={checkout.isPending}
        />
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function BillingPage() {
  return (
    <Layout>
      <div className="p-6 space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-white mb-1">Billing</h1>
          <p className="text-sm text-zinc-400">
            Manage your subscription and usage
          </p>
        </div>

        <CurrentPlanStatus />

        <div>
          <h2 className="text-xl font-semibold text-white mb-4">Plans</h2>
          <PricingTable />
        </div>
      </div>
    </Layout>
  )
}
