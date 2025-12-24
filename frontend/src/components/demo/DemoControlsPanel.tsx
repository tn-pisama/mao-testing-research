'use client'

import { Play, Pause, RefreshCw, Sparkles } from 'lucide-react'
import { clsx } from 'clsx'

interface DemoControlsPanelProps {
  isSimulating: boolean
  onToggleSimulation: () => void
  onRefresh: () => void
}

export function DemoControlsPanel({
  isSimulating,
  onToggleSimulation,
  onRefresh,
}: DemoControlsPanelProps) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-gradient-to-r from-purple-500/20 to-pink-500/20 border border-purple-500/30">
        <Sparkles size={14} className="text-purple-400" />
        <span className="text-xs font-medium text-purple-300">Demo Mode</span>
      </div>

      <div className="flex items-center gap-1 bg-slate-800 rounded-lg p-1 border border-slate-700">
        <button
          onClick={onToggleSimulation}
          className={clsx(
            'flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all',
            isSimulating
              ? 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30'
              : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
          )}
        >
          {isSimulating ? (
            <>
              <Pause size={14} />
              <span>Pause</span>
            </>
          ) : (
            <>
              <Play size={14} />
              <span>Simulate</span>
            </>
          )}
        </button>

        <button
          onClick={onRefresh}
          className="flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium bg-slate-700 text-slate-300 hover:bg-slate-600 transition-all"
        >
          <RefreshCw size={14} />
          <span>Refresh</span>
        </button>
      </div>
    </div>
  )
}
