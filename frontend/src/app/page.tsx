'use client'

export const dynamic = 'force-dynamic'

import { useState, useEffect } from 'react'
import {
  LandingHeader,
  HeroSection,
  DemoVideo,
  FeatureCards,
  SocialProof,
  QuickStart,
  ComparisonTable,
  FAQSection,
  PlatformCTA,
  WaitlistModal,
  Footer,
} from '@/components/landing'

export default function Home() {
  const [showWaitlist, setShowWaitlist] = useState(false)
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  if (!mounted) {
    return (
      <main className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="text-white">Loading...</div>
      </main>
    )
  }

  return (
    <main className="min-h-screen bg-zinc-950">
      <LandingHeader onJoinWaitlist={() => setShowWaitlist(true)} />
      <HeroSection />
      <DemoVideo />
      <FeatureCards />
      <SocialProof />
      <QuickStart />
      <ComparisonTable />
      <FAQSection />
      <PlatformCTA onJoinWaitlist={() => setShowWaitlist(true)} />
      <Footer />

      <WaitlistModal
        isOpen={showWaitlist}
        onClose={() => setShowWaitlist(false)}
      />
    </main>
  )
}
