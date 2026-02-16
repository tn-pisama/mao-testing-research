'use client'

import { Card } from '../ui/Card'
import { FlaskConical } from 'lucide-react'

interface DemoScenarioSelectorProps {
  scenarios?: Record<string, unknown> | unknown[]
  activeScenario?: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onSelectScenario?: (scenario: any) => void
  onSelect?: (id: string) => void
}

export function DemoScenarioSelector({
  scenarios,
  activeScenario,
  onSelectScenario,
  onSelect,
}: DemoScenarioSelectorProps) {
  return (
    <Card>
      <div className="text-center py-12 text-white/60 font-mono">
        <FlaskConical size={32} className="mx-auto mb-3 opacity-50" />
        <p className="text-sm">No scenarios available</p>
        <p className="text-xs mt-1 text-white/40">Create test scenarios to simulate failures</p>
      </div>
    </Card>
  )
}
