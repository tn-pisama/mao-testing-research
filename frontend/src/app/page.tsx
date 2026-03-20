'use client'

import { useState, useEffect } from 'react'
import {
  LandingHeader,
  HeroSection,
  FeatureCards,
  ComparisonTable,
  FAQSection,
  Footer,
} from '@/components/landing'

export default function Home() {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time hydration guard
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
      <LandingHeader />
      <HeroSection />
      <FeatureCards />
      <ComparisonTable />
      <FAQSection />
      <Footer />
    </main>
  )
}
