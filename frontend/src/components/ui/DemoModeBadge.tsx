'use client'

import { Badge } from './Badge'

export interface DemoModeBadgeProps {
  show: boolean
  className?: string
}

export function DemoModeBadge({ show, className }: DemoModeBadgeProps) {
  if (!show) return null

  return (
    <Badge variant="warning" size="sm" className={className}>
      [DEMO_MODE]
    </Badge>
  )
}
