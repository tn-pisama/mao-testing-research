'use client'

import { clsx } from 'clsx'
import { LucideIcon, Check } from 'lucide-react'

interface Scenario {
  title: string
  description: string
  icon: LucideIcon
}

interface DemoScenarioSelectorProps<T extends string> {
  scenarios: Record<T, Scenario>
  activeScenario: T
  onSelectScenario: (scenario: T) => void
}

export function DemoScenarioSelector<T extends string>({
  scenarios,
  activeScenario,
  onSelectScenario,
}: DemoScenarioSelectorProps<T>) {
  return (
    <>
      {(Object.entries(scenarios) as [T, Scenario][]).map(([key, scenario]) => {
        const isActive = key === activeScenario
        const Icon = scenario.icon

        return (
          <button
            key={key}
            onClick={() => onSelectScenario(key)}
            className={clsx(
              'relative p-4 rounded-xl border text-left transition-all duration-300',
              'hover:scale-[1.02] active:scale-[0.98]',
              isActive
                ? 'border-primary-500 bg-primary-500/10 shadow-lg shadow-primary-500/20'
                : 'border-slate-700 bg-slate-800/50 hover:border-slate-600 hover:bg-slate-800'
            )}
          >
            {isActive && (
              <div className="absolute top-3 right-3 p-1 rounded-full bg-primary-500">
                <Check size={12} className="text-white" />
              </div>
            )}
            <div className={clsx(
              'p-2 rounded-lg w-fit mb-3',
              isActive ? 'bg-primary-500/20' : 'bg-slate-700/50'
            )}>
              <Icon size={20} className={isActive ? 'text-primary-400' : 'text-slate-400'} />
            </div>
            <h3 className={clsx(
              'font-semibold text-sm mb-1',
              isActive ? 'text-white' : 'text-slate-300'
            )}>
              {scenario.title}
            </h3>
            <p className="text-xs text-slate-500">{scenario.description}</p>
          </button>
        )
      })}
    </>
  )
}
