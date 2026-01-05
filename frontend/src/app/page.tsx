'use client'

export const dynamic = 'force-dynamic'

import { useState, useEffect } from 'react'
import {
  LandingHeader,
  HeroSection,
  FeatureCards,
  QuickStart,
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
      <main className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="text-white">Loading...</div>
      </main>
    )
  }

  return (
    <main className="min-h-screen bg-slate-900">
      <LandingHeader onJoinWaitlist={() => setShowWaitlist(true)} />
      <HeroSection />
      <FeatureCards />
      <QuickStart />
      <PlatformCTA onJoinWaitlist={() => setShowWaitlist(true)} />
      <Footer />

      <WaitlistModal
        isOpen={showWaitlist}
        onClose={() => setShowWaitlist(false)}
      />
    </main>
  )
}
