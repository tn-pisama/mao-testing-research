'use client'

import { useState } from 'react'
import { Layout } from '@/components/common/Layout'
import { FadeIn } from '@/components/ui/Motion'
import { CurrentPlanCard } from './CurrentPlanCard'
import { BillingToggle } from './BillingToggle'
import { PricingGrid } from './PricingGrid'
import { FeatureComparisonTable } from './FeatureComparisonTable'

export function BillingPageClient() {
  const [isAnnual, setIsAnnual] = useState(false)

  return (
    <Layout>
      <div className="p-6 max-w-6xl mx-auto space-y-8">
        {/* Header */}
        <FadeIn>
          <div>
            <h1 className="text-2xl font-bold text-white mb-1">Billing</h1>
            <p className="text-sm text-zinc-400">
              Manage your subscription and usage
            </p>
          </div>
        </FadeIn>

        {/* Current plan status */}
        <CurrentPlanCard />

        {/* Plans section */}
        <FadeIn delay={0.15}>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
            <h2 className="text-xl font-semibold text-white">Choose your plan</h2>
            <BillingToggle isAnnual={isAnnual} onToggle={setIsAnnual} />
          </div>
        </FadeIn>

        <PricingGrid isAnnual={isAnnual} />

        {/* Feature comparison */}
        <FadeIn delay={0.5}>
          <FeatureComparisonTable />
        </FadeIn>
      </div>
    </Layout>
  )
}
