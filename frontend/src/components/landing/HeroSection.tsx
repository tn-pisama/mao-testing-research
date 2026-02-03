'use client'

import { useState } from 'react'
import { WaitlistModal } from './WaitlistModal'

export function HeroSection() {
  const [isModalOpen, setIsModalOpen] = useState(false)

  return (
    <>
      <section className="py-20 px-4 text-center">
        <h1 className="text-5xl md:text-6xl font-bold text-white mb-6 leading-tight">
          Stop Catching Agent Failures<br />in Production
        </h1>
        <p className="text-xl text-slate-400 max-w-3xl mx-auto mb-8">
          Test multi-agent AI systems before they hit production. PISAMA detects 17 failure modes—from infinite loops to state corruption—saving you thousands in API costs and countless hours of debugging.
        </p>

        {/* CTA Buttons */}
        <div className="flex flex-col sm:flex-row gap-4 justify-center mb-12">
          <button
            onClick={() => setIsModalOpen(true)}
            className="px-8 py-4 rounded-lg bg-sky-500 hover:bg-sky-600 text-white font-semibold text-lg transition-colors"
          >
            Start Free Trial
          </button>
          <button
            onClick={() => setIsModalOpen(true)}
            className="px-8 py-4 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-white font-semibold text-lg transition-colors"
          >
            Watch 4-Minute Demo
          </button>
        </div>

        {/* Stats Badges */}
        <div className="flex flex-wrap gap-6 justify-center items-center text-sm">
          <div className="flex items-center gap-2 text-slate-400">
            <span className="text-green-400">✓</span>
            <span>17 Failure Detectors</span>
          </div>
          <div className="flex items-center gap-2 text-slate-400">
            <span className="text-green-400">✓</span>
            <span>5 Frameworks</span>
          </div>
          <div className="flex items-center gap-2 text-slate-400">
            <span className="text-green-400">✓</span>
            <span>&lt; 2% Overhead</span>
          </div>
        </div>
      </section>

      <WaitlistModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
    </>
  )
}
