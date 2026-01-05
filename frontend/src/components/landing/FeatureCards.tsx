'use client'

import { Activity, DollarSign, Shield } from 'lucide-react'

const features = [
  {
    icon: Activity,
    title: 'Track Token Usage',
    description: 'Monitor input, output, and cache tokens for every tool call. See exactly what your Claude Code sessions consume.',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
  },
  {
    icon: DollarSign,
    title: 'Cost Analysis',
    description: 'Per-model cost breakdown with support for Opus, Sonnet, and Haiku. Know your spending before the bill arrives.',
    color: 'text-amber-400',
    bgColor: 'bg-amber-500/10',
  },
  {
    icon: Shield,
    title: 'Failure Detection',
    description: '28 MAST failure modes detected. From infinite loops to context neglect, catch issues before they cascade.',
    color: 'text-primary-400',
    bgColor: 'bg-primary-500/10',
  },
]

export function FeatureCards() {
  return (
    <section className="py-20 px-6 bg-slate-800/30">
      <div className="max-w-6xl mx-auto">
        <h2 className="text-2xl md:text-3xl font-bold text-white text-center mb-4">
          Everything runs locally
        </h2>
        <p className="text-slate-400 text-center mb-12 max-w-2xl mx-auto">
          No account required for core features. Your traces stay on your machine.
        </p>

        <div className="grid md:grid-cols-3 gap-6">
          {features.map((feature) => (
            <div
              key={feature.title}
              className="bg-slate-800 border border-slate-700 rounded-xl p-6 hover:border-slate-600 transition-colors"
            >
              <div className={`${feature.bgColor} w-12 h-12 rounded-lg flex items-center justify-center mb-4`}>
                <feature.icon className={`w-6 h-6 ${feature.color}`} />
              </div>
              <h3 className="text-lg font-semibold text-white mb-2">
                {feature.title}
              </h3>
              <p className="text-slate-400 text-sm leading-relaxed">
                {feature.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
