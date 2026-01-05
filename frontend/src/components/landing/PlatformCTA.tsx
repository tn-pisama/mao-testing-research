'use client'

import { BarChart3, Lightbulb, Zap, Shield } from 'lucide-react'

const platformFeatures = [
  { icon: BarChart3, label: 'Visual Dashboard' },
  { icon: Shield, label: '28 Failure Modes' },
  { icon: Lightbulb, label: 'AI Fix Suggestions' },
  { icon: Zap, label: 'Self-Healing' },
]

interface PlatformCTAProps {
  onJoinWaitlist: () => void
}

export function PlatformCTA({ onJoinWaitlist }: PlatformCTAProps) {
  return (
    <section className="py-20 px-6 bg-gradient-to-b from-slate-800/30 to-slate-900">
      <div className="max-w-4xl mx-auto text-center">
        <h2 className="text-2xl md:text-3xl font-bold text-white mb-4">
          PISAMA Platform
        </h2>
        <p className="text-slate-400 mb-8 max-w-2xl mx-auto">
          Connect your CLI to the platform for advanced failure detection,
          AI-powered fix suggestions, and self-healing automation.
        </p>

        {/* Feature Pills */}
        <div className="flex flex-wrap items-center justify-center gap-3 mb-10">
          {platformFeatures.map((feature) => (
            <div
              key={feature.label}
              className="flex items-center gap-2 bg-slate-800 border border-slate-700 rounded-full px-4 py-2"
            >
              <feature.icon className="w-4 h-4 text-primary-400" />
              <span className="text-sm text-slate-300">{feature.label}</span>
            </div>
          ))}
        </div>

        {/* CTA */}
        <button
          onClick={onJoinWaitlist}
          className="inline-flex items-center gap-2 bg-primary-600 hover:bg-primary-500 text-white font-medium px-8 py-3 rounded-lg transition-colors text-lg"
        >
          Join the Waitlist
        </button>
        <p className="text-slate-500 text-sm mt-4">
          Be the first to know when the platform launches
        </p>
      </div>
    </section>
  )
}
