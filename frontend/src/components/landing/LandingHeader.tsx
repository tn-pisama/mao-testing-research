'use client'

import Link from 'next/link'
import { Button } from '../ui/Button'

interface LandingHeaderProps {
  onJoinWaitlist?: () => void
}

export function LandingHeader({ onJoinWaitlist }: LandingHeaderProps) {
  return (
    <header className="flex items-center justify-between py-2 px-4 border-b border-[#00ff00] bg-black font-mono">
      <div className="text-sm font-semibold text-[#00ff00]">{'[MAO_TESTING]'}</div>
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
