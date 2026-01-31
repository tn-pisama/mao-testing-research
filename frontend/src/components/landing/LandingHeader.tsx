'use client'

import Link from 'next/link'
import { Button } from '../ui/Button'

interface LandingHeaderProps {
  onJoinWaitlist?: () => void
}

export function LandingHeader({ onJoinWaitlist }: LandingHeaderProps) {
  return (
    <header className="flex items-center justify-between py-6 px-8 border-b border-neutral-200 bg-white">
      <div className="text-base font-medium text-black">MAO Testing</div>
      <div className="flex items-center gap-3">
        {onJoinWaitlist && (
          <Button variant="primary" onClick={onJoinWaitlist} size="sm">
            Join Waitlist
          </Button>
        )}
        <Link href="/dashboard">
          <Button variant="secondary" size="sm">Dashboard</Button>
        </Link>
      </div>
    </header>
  )
}
