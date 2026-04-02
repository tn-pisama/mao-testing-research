'use client'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/ui/Skeleton'
import { FadeIn } from '@/components/ui/Motion'
import { UsageBar } from './UsageBar'
import { useBillingStatus, useBillingPortal } from '@/hooks/useBilling'
import { CreditCard, ExternalLink, AlertTriangle } from 'lucide-react'

const statusBadge: Record<
  string,
  { variant: 'success' | 'warning' | 'error' | 'info' | 'default'; label: string }
> = {
  active: { variant: 'success', label: 'Active' },
  trialing: { variant: 'info', label: 'Trial' },
  past_due: { variant: 'error', label: 'Past Due' },
  canceled: { variant: 'error', label: 'Canceled' },
  incomplete: { variant: 'warning', label: 'Incomplete' },
  free: { variant: 'default', label: 'Free' },
}

export function CurrentPlanCard() {
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
      <div className="rounded-xl bg-zinc-900/60 border border-zinc-800 overflow-hidden">
        <div className="h-1 bg-gradient-to-r from-blue-500 via-violet-500 to-blue-500" />
        <div className="p-6">
          <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-6">
            <div className="flex items-start gap-4">
              <Skeleton className="h-12 w-12 rounded-xl" />
              <div>
                <Skeleton className="h-6 w-32 mb-2" />
                <Skeleton className="h-4 w-48 mb-3" />
                <Skeleton className="h-9 w-40" />
              </div>
            </div>
            <div className="lg:w-80 space-y-4">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (!status) {
    return (
      <div className="rounded-xl bg-zinc-900/60 border border-zinc-800 p-6">
        <p className="text-zinc-400 text-sm">Unable to load billing status.</p>
      </div>
    )
  }

  const badge = statusBadge[status.status] ?? {
    variant: 'default' as const,
    label: status.status,
  }
  const isFree = status.plan === 'free' || status.status === 'free'

  return (
    <FadeIn delay={0.1}>
      <div className="rounded-xl bg-zinc-900/60 border border-zinc-800 overflow-hidden">
        {/* Accent stripe */}
        <div className="h-1 bg-gradient-to-r from-blue-500 via-violet-500 to-blue-500" />

        <div className="p-6">
          <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-6">
            {/* Left: Plan info */}
            <div className="flex items-start gap-4">
              <div className="p-3 bg-blue-500/10 rounded-xl border border-blue-500/20 flex-shrink-0">
                <CreditCard className="w-6 h-6 text-blue-400" />
              </div>
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="text-lg font-semibold text-white">
                    {status.plan_name}
                  </h3>
                  <Badge variant={badge.variant} size="sm">
                    {badge.label}
                  </Badge>
                </div>
                {status.current_period_end && (
                  <p className="text-sm text-zinc-400 mb-3">
                    Renews{' '}
                    {new Date(status.current_period_end).toLocaleDateString(
                      'en-US',
                      { month: 'long', day: 'numeric', year: 'numeric' }
                    )}
                  </p>
                )}
                {!status.current_period_end && isFree && (
                  <p className="text-sm text-zinc-400 mb-3">No active subscription</p>
                )}
                {!isFree && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleManage}
                    isLoading={portal.isPending}
                  >
                    Manage Subscription
                    <ExternalLink size={14} className="ml-2" />
                  </Button>
                )}
              </div>
            </div>

            {/* Right: Usage */}
            <div className="lg:w-80 space-y-3">
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

          {/* Cancellation warning */}
          {status.cancel_at_period_end && (
            <div className="flex items-center gap-2 p-3 mt-4 rounded-lg bg-amber-500/10 border border-amber-500/20">
              <AlertTriangle size={16} className="text-amber-400 flex-shrink-0" />
              <p className="text-sm text-amber-300">
                Your subscription will cancel at the end of the current period.
                You can reactivate from the billing portal.
              </p>
            </div>
          )}
        </div>
      </div>
    </FadeIn>
  )
}
