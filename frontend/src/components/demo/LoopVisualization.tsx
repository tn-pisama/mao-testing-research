'use client'

import { useEffect, useState } from 'react'
import { clsx } from 'clsx'
import { RotateCcw, ArrowRight } from 'lucide-react'
import { AgentInfo } from '@/components/agents'

interface LoopVisualizationProps {
  agents: AgentInfo[]
}

export function LoopVisualization({ agents }: LoopVisualizationProps) {
  const [activeStep, setActiveStep] = useState(0)
  const loopAgents = agents.slice(0, 3)

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveStep((prev) => (prev + 1) % loopAgents.length)
    }, 1500)
    return () => clearInterval(interval)
  }, [loopAgents.length])

  return (
    <div className="h-[600px] bg-slate-900 rounded-xl border border-red-500/30 overflow-hidden relative">
      <div className="absolute inset-0 bg-gradient-to-br from-red-500/5 to-orange-500/5" />
      
      <div className="absolute top-4 left-4 right-4 flex items-center justify-between">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-red-500/20 border border-red-500/30">
          <RotateCcw size={14} className="text-red-400 animate-spin" />
          <span className="text-xs font-medium text-red-400">Loop Detected</span>
        </div>
        <div className="text-xs text-slate-500">
          Iteration: <span className="text-white font-mono">{Math.floor(Date.now() / 1500) % 100}</span>
        </div>
      </div>

      <div className="absolute inset-0 flex items-center justify-center">
        <div className="relative w-80 h-80">
          <svg className="absolute inset-0 w-full h-full" viewBox="0 0 320 320">
            <circle
              cx="160"
              cy="160"
              r="120"
              fill="none"
              stroke="rgba(239, 68, 68, 0.2)"
              strokeWidth="2"
              strokeDasharray="8 4"
            />
            <circle
              cx="160"
              cy="160"
              r="120"
              fill="none"
              stroke="rgba(239, 68, 68, 0.6)"
              strokeWidth="3"
              strokeDasharray="60 300"
              strokeLinecap="round"
              className="animate-spin-slow origin-center"
              style={{ transformOrigin: '160px 160px' }}
            />
          </svg>

          {loopAgents.map((agent, index) => {
            const angle = (index / loopAgents.length) * 2 * Math.PI - Math.PI / 2
            const x = 160 + 120 * Math.cos(angle)
            const y = 160 + 120 * Math.sin(angle)
            const isActive = index === activeStep

            return (
              <div
                key={agent.id}
                className={clsx(
                  'absolute transform -translate-x-1/2 -translate-y-1/2 transition-all duration-500',
                  isActive && 'scale-110 z-10'
                )}
                style={{ left: x, top: y }}
              >
                <div
                  className={clsx(
                    'p-4 rounded-xl border-2 bg-slate-800 min-w-[120px] text-center transition-all duration-500',
                    isActive
                      ? 'border-red-500 shadow-lg shadow-red-500/30'
                      : 'border-slate-700'
                  )}
                >
                  {isActive && (
                    <div className="absolute -inset-1 rounded-xl bg-red-500/20 animate-pulse -z-10" />
                  )}
                  <div className="font-semibold text-white text-sm">{agent.name}</div>
                  <div className="text-xs text-slate-400 mt-1">{agent.stepCount} steps</div>
                  {isActive && (
                    <div className="mt-2 text-[10px] text-red-400 font-medium animate-pulse">
                      ACTIVE
                    </div>
                  )}
                </div>
              </div>
            )
          })}

          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-center">
            <RotateCcw size={32} className="text-red-500/50 mx-auto animate-spin-slow" />
            <div className="text-sm text-red-400 mt-2 font-medium">Infinite Loop</div>
            <div className="text-xs text-slate-500 mt-1">Pattern repeating</div>
          </div>
        </div>
      </div>

      <div className="absolute bottom-4 left-4 right-4">
        <div className="flex items-center justify-between text-xs text-slate-500 mb-2">
          <span>Loop Pattern</span>
          <span className="text-red-400">High Confidence: 94%</span>
        </div>
        <div className="flex items-center justify-center gap-2 p-3 rounded-lg bg-slate-800/80 border border-slate-700">
          {loopAgents.map((agent, index) => (
            <div key={agent.id} className="flex items-center gap-2">
              <span
                className={clsx(
                  'px-2 py-1 rounded text-xs font-medium transition-colors',
                  index === activeStep
                    ? 'bg-red-500/20 text-red-400'
                    : 'bg-slate-700 text-slate-400'
                )}
              >
                {agent.name}
              </span>
              {index < loopAgents.length - 1 && (
                <ArrowRight size={12} className="text-slate-600" />
              )}
            </div>
          ))}
          <ArrowRight size={12} className="text-slate-600" />
          <span className="text-red-400 text-xs">↻ repeat</span>
        </div>
      </div>
    </div>
  )
}
