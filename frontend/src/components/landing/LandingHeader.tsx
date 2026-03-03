'use client'

import Link from 'next/link'
import { Button } from '../ui/Button'

interface LandingHeaderProps {
  onJoinWaitlist?: () => void
}

export function LandingHeader({ onJoinWaitlist }: LandingHeaderProps) {
  return (
    <header className="flex items-center justify-between py-2 px-4 border-b border-zinc-800 bg-zinc-950">
      <div className="text-sm font-semibold text-white">{'[PISAMA]'}</div>
      <div className="flex items-center gap-2">
        {onJoinWaitlist && (
          <Button variant="primary" onClick={onJoinWaitlist} size="sm">
            WAITLIST
          </Button>
        )}
        <Link href="/dashboard">
          <Button variant="secondary" size="sm">DASHBOARD</Button>
        </Link>
      </div>
    </header>
  )
}
