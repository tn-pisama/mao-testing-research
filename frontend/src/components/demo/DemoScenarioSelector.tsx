'use client'

import { Card } from '../ui/Card'

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
      <div className="text-center py-8 text-slate-400">
        <p className="text-sm">Scenario selector coming soon</p>
      </div>
    </Card>
  )
}
