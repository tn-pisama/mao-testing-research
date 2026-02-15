'use client'

import { Badge } from './Badge'

export interface DemoModeBadgeProps {
  show: boolean
  className?: string
}

/**
 * Badge component to indicate when demo/mock data is being displayed
 * Styled for the Neon Dark (Terminal/Hacker) theme
 */
export function DemoModeBadge({ show, className }: DemoModeBadgeProps) {
  if (!show) return null

  return (
    <Badge variant="warning" size="sm" className={className}>
      [DEMO_MODE]
    </Badge>
  )
}
