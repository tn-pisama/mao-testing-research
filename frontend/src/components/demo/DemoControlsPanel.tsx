'use client'

import { Card } from '../ui/Card'
import { Button } from '../ui/Button'

interface DemoControlsPanelProps {
  onAction?: (action: string) => void
  isSimulating?: boolean
  onToggleSimulation?: () => void
  onRefresh?: () => void
}

export function DemoControlsPanel({
  onAction,
  isSimulating,
  onToggleSimulation,
  onRefresh,
}: DemoControlsPanelProps) {
  return (
    <Card>
      <div className="p-4 flex items-center gap-2">
        <Button
          variant={isSimulating ? 'danger' : 'primary'}
          size="sm"
          onClick={onToggleSimulation}
        >
          {isSimulating ? 'Stop' : 'Start'} Simulation
        </Button>
        <Button variant="secondary" size="sm" onClick={onRefresh}>
          Refresh
        </Button>
      </div>
    </Card>
  )
}
