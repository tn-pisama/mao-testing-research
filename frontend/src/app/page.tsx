'use client'

import { SignIn, SignedIn, SignedOut } from '@clerk/nextjs'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'

export default function Home() {
  const router = useRouter()

  return (
    <main className="min-h-screen bg-slate-900 flex items-center justify-center">
      <SignedOut>
        <SignIn fallbackRedirectUrl="/dashboard" />
      </SignedOut>
      <SignedIn>
        <div className="text-white">Redirecting...</div>
        <RedirectToDashboard />
      </SignedIn>
    </main>
  )
}

function RedirectToDashboard() {
  const router = useRouter()
  useEffect(() => {
    router.push('/dashboard')
  }, [router])
  return null
}
