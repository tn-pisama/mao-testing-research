'use client'

export const dynamic = 'force-dynamic'

import { useEffect, useState } from 'react'

export default function Home() {
  const [mounted, setMounted] = useState(false)
  const [hasClerk, setHasClerk] = useState(false)

  useEffect(() => {
    // Check for Clerk key on client side to avoid SSR issues
    setHasClerk(!!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
    setMounted(true)
  }, [])

  // Show loading state until mounted
  if (!mounted) {
    return (
      <main className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="text-white">Loading...</div>
      </main>
    )
  }

  // When Clerk is not configured, just redirect to dashboard
  if (!hasClerk) {
    return <RedirectToDashboard />
  }

  // Only import Clerk components when Clerk is configured and mounted
  const ClerkComponents = require('@clerk/nextjs')
  const { SignIn, SignedIn, SignedOut } = ClerkComponents

  return (
    <main className="min-h-screen bg-slate-900 flex items-center justify-center">
      <SignedOut>
        <SignIn fallbackRedirectUrl="/dashboard" />
      </SignedOut>
      <SignedIn>
        <RedirectToDashboard />
      </SignedIn>
    </main>
  )
}

function RedirectToDashboard() {
  useEffect(() => {
    window.location.href = '/dashboard'
  }, [])
  return (
    <main className="min-h-screen bg-slate-900 flex items-center justify-center">
      <div className="text-white">Redirecting to dashboard...</div>
    </main>
  )
}
