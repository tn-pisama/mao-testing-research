'use client'

import Link from 'next/link'
import { Button } from '../ui/Button'

export function PlatformCTA() {
  return (
    <section className="py-16 text-center">
      <h2 className="text-3xl font-bold text-white mb-4">Get Started</h2>
      <div className="flex justify-center gap-4">
        <Link href="/dashboard">
          <Button size="lg" variant="primary">Go to Dashboard</Button>
        </Link>
        <Link href="/docs/getting-started">
          <Button size="lg" variant="secondary">Read the Docs</Button>
        </Link>
      </div>
    </section>
  )
}
