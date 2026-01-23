'use client'

import { Card } from '../ui/Card'
import { Button } from '../ui/Button'
import { Compass } from 'lucide-react'

interface GuidedWalkthroughProps {
  step?: number
  onNext?: () => void
  onComplete?: () => void
  onSkip?: () => void
}

export function GuidedWalkthrough({ step, onNext, onComplete, onSkip }: GuidedWalkthroughProps) {
  return (
    <Card>
      <div className="text-center py-12 text-slate-400">
        <Compass size={32} className="mx-auto mb-3 opacity-50" />
        <p className="text-sm">Welcome to MAO Testing</p>
        <p className="text-xs mt-1">Explore the platform to get started</p>
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
