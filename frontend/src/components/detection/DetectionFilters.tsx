import { Filter } from 'lucide-react'
import { cn } from '@/lib/utils'
import { detectionTypeConfig } from './DetectionTypeConfig'
import type { DetectionType, Severity } from './DetectionTypeConfig'

interface DetectionFiltersProps {
  typeFilter: DetectionType
  setTypeFilter: (type: DetectionType) => void
  severityFilter: Severity
  setSeverityFilter: (severity: Severity) => void
  showValidated: boolean
  setShowValidated: (show: boolean) => void
  stats: {
    byType: Record<string, number>
  }
}

export function DetectionFilters({
  typeFilter,
  setTypeFilter,
  severityFilter,
  setSeverityFilter,
  showValidated,
  setShowValidated,
  stats,
}: DetectionFiltersProps) {
  return (
    <div className="lg:col-span-1 space-y-4">
      <div className="p-4 rounded-xl bg-zinc-800/50 border border-zinc-700">
        <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
          <Filter size={14} />
          Filters
        </h3>

        <div className="space-y-4">
          <div>
            <label className="text-xs text-zinc-400 mb-2 block">Detection Type</label>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value as DetectionType)}
              className="w-full px-3 py-2 rounded-lg bg-zinc-900 border border-zinc-700 text-white text-sm focus:outline-none focus:border-blue-500"
            >
              <option value="all">All Types</option>
              <optgroup label="System Design">
                <option value="specification_mismatch">Spec Mismatch (F1)</option>
                <option value="poor_decomposition">Poor Decomposition (F2)</option>
                <option value="state_corruption">State Corruption (F3/F4)</option>
                <option value="flawed_workflow">Flawed Workflow (F5)</option>
              </optgroup>
              <optgroup label="Inter-Agent">
                <option value="task_derailment">Task Derailment (F6)</option>
                <option value="context_neglect">Context Neglect (F7)</option>
                <option value="infinite_loop">Infinite Loop (F8/F9)</option>
                <option value="communication_breakdown">Communication Breakdown (F10)</option>
                <option value="persona_drift">Persona Drift (F11)</option>
              </optgroup>
              <optgroup label="Coordination">
                <option value="coordination_deadlock">Deadlock (F12-F14)</option>
              </optgroup>
            </select>
          </div>

          <div>
            <label className="text-xs text-zinc-400 mb-2 block">Severity</label>
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value as Severity)}
              className="w-full px-3 py-2 rounded-lg bg-zinc-900 border border-zinc-700 text-white text-sm focus:outline-none focus:border-blue-500"
            >
              <option value="all">All Severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={showValidated}
              onChange={(e) => setShowValidated(e.target.checked)}
              className="rounded border-zinc-600 bg-zinc-900 text-blue-500 focus:ring-blue-500"
            />
            <span className="text-sm text-zinc-300">Show Validated</span>
          </label>
        </div>
      </div>

      <div className="p-4 rounded-xl bg-zinc-800/50 border border-zinc-700">
        <h3 className="text-sm font-semibold text-white mb-3">By Type</h3>
        <div className="space-y-2">
          {Object.entries(stats.byType).map(([type, count]) => {
            const config = detectionTypeConfig[type]
            const Icon = config.icon
            return (
              <button
                key={type}
                onClick={() => setTypeFilter(type as DetectionType)}
                className={cn(
                  'w-full flex items-center justify-between p-2 rounded-lg transition-colors',
                  typeFilter === type ? 'bg-zinc-700' : 'hover:bg-zinc-700/50'
                )}
              >
                <div className="flex items-center gap-2">
                  <Icon size={14} className={config.color} />
                  <span className="text-sm text-zinc-300">{config.label}</span>
                </div>
                <span className="text-sm font-medium text-white">{count}</span>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
