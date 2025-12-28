'use client'

import { SignIn, SignedIn, SignedOut } from '@clerk/nextjs'
import { useEffect } from 'react'

export default function Home() {
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
  return <div className="text-white">Redirecting to dashboard...</div>
}
