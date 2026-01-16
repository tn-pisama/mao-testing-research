'use client'

import { Button } from '../ui/Button'

export function WalkthroughTrigger({ onClick }: { onClick?: () => void }) {
  return (
    <Button variant="ghost" onClick={onClick}>
      Take a Tour
    </Button>
  )
}
