'use client'

import { Card } from '../ui/Card'

export function FailureCard({ detection }: { detection?: unknown }) {
  return (
    <Card>
      <div className="text-center py-8 text-slate-400">
        <p className="text-sm">Failure card coming soon</p>
      </div>
    </Card>
  )
}
