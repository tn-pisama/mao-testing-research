'use client'

import { Card } from '../ui/Card'
import { Button } from '../ui/Button'

interface GuidedWalkthroughProps {
  step?: number
  onNext?: () => void
  onComplete?: () => void
  onSkip?: () => void
}

export function GuidedWalkthrough({ step, onNext, onComplete, onSkip }: GuidedWalkthroughProps) {
  return (
    <Card>
      <div className="text-center py-8 text-slate-400">
        <p className="text-sm">Guided walkthrough coming soon</p>
        <div className="mt-4 flex justify-center gap-2">
          <Button variant="ghost" size="sm" onClick={onSkip}>
            Skip
          </Button>
          <Button size="sm" onClick={onComplete}>
            Complete
          </Button>
        </div>
      </div>
    </Card>
  )
}

export function WalkthroughTrigger({ onClick }: { onClick?: () => void }) {
  return (
    <Button variant="ghost" onClick={onClick}>
      Take a Tour
    </Button>
  )
}
