'use client'

import { Shield } from 'lucide-react'

export function HeroSection() {
  return (
    <section className="relative py-10 sm:py-14 overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-b from-blue-600/5 via-transparent to-transparent" />

      <div className="relative max-w-4xl mx-auto px-6 text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-sm mb-5">
          <Shield size={14} />
          Agent Forensics Platform
        </div>

        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-white tracking-tight leading-[1.1] mb-4">
          Find out why your
          <br />
          <span className="text-blue-400">AI agent failed</span>
        </h1>

        <p className="text-lg sm:text-xl text-zinc-400 max-w-2xl mx-auto leading-relaxed">
          Self-healing diagnostics for multi-agent systems. Detect infinite loops,
          state corruption, and persona drift — then fix them automatically.
        </p>
      </div>
    </section>
  )
}
