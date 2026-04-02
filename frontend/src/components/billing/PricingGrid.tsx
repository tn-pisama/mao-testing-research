'use client'

import { StaggerContainer, StaggerItem } from '@/components/ui/Motion'
import { Skeleton } from '@/components/ui/Skeleton'
import { PricingCard } from './PricingCard'
import { planDisplayData } from './billing-data'
import { useBillingPlans, useBillingStatus, useCreateCheckout } from '@/hooks/useBilling'
import type { BillingPlan } from '@/hooks/useBilling'

interface PricingGridProps {
  isAnnual: boolean
}

export function PricingGrid({ isAnnual }: PricingGridProps) {
  const { plans, isLoading: plansLoading } = useBillingPlans()
  const { status } = useBillingStatus()
  const checkout = useCreateCheckout()

  const handleSelect = async (plan: BillingPlan) => {
    const result = await checkout.mutateAsync({ plan: plan.slug, annual: isAnnual })
    if (result.checkout_url) {
      window.location.href = result.checkout_url
    }
  }

  if (plansLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 lg:gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="p-6 rounded-xl bg-zinc-900 border border-zinc-800">
            <Skeleton className="h-4 w-20 mb-2" />
            <Skeleton className="h-6 w-24 mb-2" />
            <Skeleton className="h-10 w-28 mb-6" />
            <div className="space-y-2.5">
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
  const planBySlug = new Map<string, BillingPlan>()
  for (const p of plans) {
    planBySlug.set(p.slug, p)
  }

  return (
    <StaggerContainer stagger={0.08} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 lg:gap-4 lg:items-start">
      {planDisplayData.map((display) => {
        const plan = planBySlug.get(display.slug)
        const isPurchasable =
          plan != null &&
          (display.slug === 'pro' || display.slug === 'team') &&
          (isAnnual
            ? !!plan.stripe_price_id_annual
            : !!plan.stripe_price_id_monthly)

        return (
          <StaggerItem key={display.slug}>
            <PricingCard
              display={display}
              isAnnual={isAnnual}
              isCurrent={currentSlug === display.slug}
              isPopular={display.slug === 'pro'}
              isPurchasable={isPurchasable}
              onSelect={() => plan && handleSelect(plan)}
              isLoading={checkout.isPending}
            />
          </StaggerItem>
        )
      })}
    </StaggerContainer>
  )
}
