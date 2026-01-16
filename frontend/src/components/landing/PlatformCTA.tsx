'use client'

import Link from 'next/link'
import { Button } from '../ui/Button'

interface PlatformCTAProps {
  onJoinWaitlist?: () => void
}

export function PlatformCTA({ onJoinWaitlist }: PlatformCTAProps) {
  return (
    <section className="py-16 text-center">
      <h2 className="text-3xl font-bold text-white mb-4">Get Started</h2>
      <div className="flex justify-center gap-4">
        {onJoinWaitlist && (
          <Button size="lg" variant="primary" onClick={onJoinWaitlist}>
            Join Waitlist
          </Button>
        )}
        <Link href="/dashboard">
          <Button size="lg" variant="secondary">Go to Dashboard</Button>
        </Link>
      </div>
    </section>
  )
}
