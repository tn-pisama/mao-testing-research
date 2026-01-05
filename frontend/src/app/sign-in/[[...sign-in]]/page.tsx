'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'

export default function SignInPage() {
  const [mounted, setMounted] = useState(false)
  const [hasClerk, setHasClerk] = useState(false)

  useEffect(() => {
    setHasClerk(!!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
    setMounted(true)
  }, [])

  if (!mounted) {
    return (
      <main className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="text-white">Loading...</div>
      </main>
    )
  }

  if (!hasClerk) {
    // No Clerk configured - redirect to dashboard
    return (
      <main className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="text-center">
          <p className="text-slate-400 mb-4">Authentication not configured</p>
          <Link href="/dashboard" className="text-primary-400 hover:text-primary-300">
            Go to Dashboard →
          </Link>
        </div>
      </main>
    )
  }

  // Dynamically import Clerk SignIn
  const { SignIn } = require('@clerk/nextjs')

  return (
    <main className="min-h-screen bg-slate-900 flex flex-col items-center justify-center p-4">
      <Link
        href="/"
        className="absolute top-6 left-6 flex items-center gap-2 text-slate-400 hover:text-white transition-colors"
      >
        <ArrowLeft size={16} />
        <span>Back</span>
      </Link>

      <SignIn
        appearance={{
          elements: {
            rootBox: 'mx-auto',
            card: 'bg-slate-800 border border-slate-700',
          },
        }}
        fallbackRedirectUrl="/dashboard"
      />
    </main>
  )
}
