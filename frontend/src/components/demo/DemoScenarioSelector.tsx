'use client'

import { Card, CardContent } from '../ui/Card'
import { RefreshCw, AlertTriangle, Brain, CheckCircle, Shield } from 'lucide-react'
import type { DemoScenario } from '@/lib/demo-fixtures'

const ICON_MAP: Record<string, any> = {
  RefreshCw,
  AlertTriangle,
  Brain,
  CheckCircle,
  Shield,
}

interface DemoScenarioSelectorProps {
  scenarios: DemoScenario[]
  activeScenarioId: string | null
  onSelect: (id: string) => void
}

export function DemoScenarioSelector({
  scenarios,
  activeScenarioId,
  onSelect,
}: DemoScenarioSelectorProps) {
  return (
    <>
      {scenarios.map((scenario) => {
        const Icon = ICON_MAP[scenario.icon] || AlertTriangle
        const isActive = activeScenarioId === scenario.id
        const hasIssues = scenario.detections.length > 0

        return (
          <Card
            key={scenario.id}
            className={`cursor-pointer transition-all ${
              isActive
                ? 'border-blue-500 bg-blue-500/10 ring-1 ring-blue-500/30'
                : 'border-zinc-800 hover:border-zinc-600 bg-zinc-900'
            }`}
            onClick={() => onSelect(scenario.id)}
          >
            <CardContent className="p-4">
              <div className="flex items-start gap-3">
                <div
                  className={`p-2 rounded-lg ${
                    isActive
                      ? 'bg-blue-500/20'
                      : hasIssues
                      ? 'bg-red-500/10'
                      : 'bg-green-500/10'
                  }`}
                >
                  <Icon
                    size={20}
                    className={
                      isActive
                        ? 'text-blue-400'
                        : hasIssues
                        ? 'text-red-400'
                        : 'text-green-400'
                    }
                  />
                </div>
                <div className="flex-1 min-w-0">
                  <h3
                    className={`font-medium text-sm ${
                      isActive ? 'text-blue-300' : 'text-zinc-200'
                    }`}
                  >
                    {scenario.title}
                  </h3>
                  <p className="text-xs text-zinc-500 mt-0.5 line-clamp-2">
                    {scenario.description}
                  </p>
                  <div className="flex items-center gap-2 mt-2">
                    <span className="text-xs text-zinc-600">{scenario.framework}</span>
                    {hasIssues && (
                      <span className="text-xs px-1.5 py-0.5 rounded bg-red-500/10 text-red-400">
                        {scenario.detections.length} issue{scenario.detections.length > 1 ? 's' : ''}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )
      })}
    </>
  )
}
