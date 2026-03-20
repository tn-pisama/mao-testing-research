'use client'

import Link from 'next/link'
import { Shield } from 'lucide-react'
import { Button } from '../ui/Button'

export function LandingHeader() {
  return (
    <header className="flex items-center justify-between py-2 px-4 border-b border-zinc-800 bg-zinc-950">
      <Link href="/" className="flex items-center gap-2">
        <Shield className="h-5 w-5 text-blue-500" />
        <span className="text-sm font-semibold text-white">Pisama</span>
      </Link>
      <div className="flex items-center gap-2">
        <Link href="/sign-in">
          <Button variant="ghost" size="sm">Login</Button>
        </Link>
        <Link href="/sign-up">
          <Button variant="primary" size="sm">Join Waitlist</Button>
        </Link>
      </div>
    </header>
  )
}
