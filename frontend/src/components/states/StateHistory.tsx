'use client'

import { Card } from '../ui/Card'

interface StateHistoryProps {
  states?: unknown[]
  isLoading?: boolean
}

export function StateHistory({ states, isLoading }: StateHistoryProps) {
  if (isLoading) {
    return (
      <Card>
        <div className="text-center py-8 text-slate-400">
          <p className="text-sm">Loading state history...</p>
        </div>
      </Card>
    )
  }

  return (
    <Card>
      <div className="text-center py-8 text-slate-400">
        <p className="text-sm">State history coming soon</p>
        {states && states.length > 0 && (
          <p className="text-xs mt-2">{states.length} states</p>
        )}
      </div>
    </Card>
  )
}
