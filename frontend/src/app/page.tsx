'use client'

export const dynamic = 'force-dynamic'

import { useEffect } from 'react'

const hasClerk = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY

export default function Home() {
  // When Clerk is not configured, just redirect to dashboard
  if (!hasClerk) {
    return <RedirectToDashboard />
  }

  // Only import Clerk components when Clerk is configured
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
