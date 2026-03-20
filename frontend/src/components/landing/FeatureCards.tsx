'use client'

import { AlertTriangle, Search, Sparkles, RotateCcw, BarChart3, Shield } from 'lucide-react'

const features = [
  {
    icon: AlertTriangle,
    title: 'Failure Detection',
    description: 'Automatically detect infinite loops, state corruption, persona drift, deadlocks, and 13 other failure modes in real time.',
    color: 'text-red-400',
    bgColor: 'bg-red-500/10',
  },
  {
    icon: Search,
    title: 'Root Cause Analysis',
    description: 'Trace failures back to the exact agent, step, and state transition that caused the problem. No more guessing.',
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/10',
  },
  {
    icon: Sparkles,
    title: 'Self-Healing Fixes',
    description: 'AI-generated fix suggestions with safe staging, one-click apply, and automatic rollback if things go wrong.',
    color: 'text-violet-400',
    bgColor: 'bg-violet-500/10',
  },
  {
    icon: RotateCcw,
    title: 'Replay & Debug',
    description: 'Replay any workflow execution step-by-step. Inspect agent states, messages, and decisions at every point.',
    color: 'text-amber-400',
    bgColor: 'bg-amber-500/10',
  },
  {
    icon: BarChart3,
    title: 'Quality Scoring',
    description: 'Continuous quality grades for every workflow. Track reliability, cost efficiency, and performance over time.',
    color: 'text-green-400',
    bgColor: 'bg-green-500/10',
  },
  {
    icon: Shield,
    title: 'Framework Agnostic',
    description: 'Works with LangGraph, CrewAI, AutoGen, n8n, Dify, and any custom framework via OpenTelemetry.',
    color: 'text-cyan-400',
    bgColor: 'bg-cyan-500/10',
  },
]

export function FeatureCards() {
  return (
    <section className="py-14 px-6">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-14">
          <h2 className="text-3xl font-bold text-white mb-3">
            Everything you need to ship reliable agents
          </h2>
          <p className="text-zinc-400 text-lg max-w-2xl mx-auto">
            From detection to remediation, Pisama handles the full lifecycle of agent failure management.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {features.map((feature) => {
            const Icon = feature.icon
            return (
              <div
                key={feature.title}
                className="p-6 rounded-xl bg-zinc-900 border border-zinc-800 hover:border-zinc-700 transition-colors"
              >
                <div className={`inline-flex p-2.5 rounded-lg ${feature.bgColor} mb-4`}>
                  <Icon size={20} className={feature.color} />
                </div>
                <h3 className="text-base font-semibold text-white mb-2">{feature.title}</h3>
                <p className="text-sm text-zinc-400 leading-relaxed">{feature.description}</p>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
