'use client'

import Link from 'next/link'
import { Button } from '../ui/Button'

interface LandingHeaderProps {
  onJoinWaitlist?: () => void
}

export function LandingHeader({ onJoinWaitlist }: LandingHeaderProps) {
  return (
    <header className="flex items-center justify-between py-4 px-6">
      <div className="text-xl font-bold text-neutral-900">MAO Testing</div>
      <div className="flex items-center gap-4">
        {onJoinWaitlist && (
          <Button variant="primary" onClick={onJoinWaitlist}>
            Join Waitlist
          </Button>
        )}
        <Link href="/dashboard">
          <Button variant="secondary">Dashboard</Button>
        </Link>
      </div>
    </header>
  )
}
