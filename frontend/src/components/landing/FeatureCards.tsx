'use client'

const features = [
  {
    title: 'Failure Detection',
    description: 'Automatically detect infinite loops, state corruption, persona drift, deadlocks, and 13 other failure modes in real time.',
    accent: 'border-l-red-400',
  },
  {
    title: 'Root Cause Analysis',
    description: 'Trace failures back to the exact agent, step, and state transition that caused the problem. No more guessing.',
    accent: 'border-l-blue-400',
  },
  {
    title: 'Self-Healing Fixes',
    description: 'AI-generated fix suggestions with safe staging, one-click apply, and automatic rollback if things go wrong.',
    accent: 'border-l-violet-400',
  },
  {
    title: 'Replay and Debug',
    description: 'Replay any workflow execution step-by-step. Inspect agent states, messages, and decisions at every point.',
    accent: 'border-l-amber-400',
  },
  {
    title: 'Quality Scoring',
    description: 'Continuous quality grades for every workflow. Track reliability, cost efficiency, and performance over time.',
    accent: 'border-l-green-400',
  },
  {
    title: 'Framework Agnostic',
    description: 'Works with LangGraph, CrewAI, AutoGen, n8n, Dify, OpenClaw, and any custom framework via OpenTelemetry.',
    accent: 'border-l-cyan-400',
  },
]

export function FeatureCards() {
  return (
    <section className="py-14 px-6">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-10">
          <h2 className="text-3xl font-bold text-white mb-3">
            Everything you need to ship reliable agents
          </h2>
          <p className="text-zinc-400 text-lg max-w-2xl mx-auto">
            From detection to remediation, Pisama handles the full lifecycle of agent failure management.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {features.map((feature) => (
            <div
              key={feature.title}
              className={`p-5 rounded-lg bg-zinc-900 border border-zinc-800 border-l-2 ${feature.accent} hover:border-zinc-700 transition-colors`}
            >
              <h3 className="text-base font-semibold text-white mb-2">{feature.title}</h3>
              <p className="text-sm text-zinc-400 leading-relaxed">{feature.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
