'use client'

import Link from 'next/link'
import { ArrowRight, Shield } from 'lucide-react'

export function HeroSection() {
  return (
    <section className="relative py-16 sm:py-20 overflow-hidden">
      {/* Subtle gradient background */}
      <div className="absolute inset-0 bg-gradient-to-b from-blue-600/5 via-transparent to-transparent" />

      <div className="relative max-w-4xl mx-auto px-6 text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-sm mb-8">
          <Shield size={14} />
          Agent Forensics Platform
        </div>

        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-white tracking-tight leading-[1.1] mb-6">
          Find out why your
          <br />
          <span className="text-blue-400">AI agent failed</span>
        </h1>

        <p className="text-lg sm:text-xl text-zinc-400 max-w-2xl mx-auto mb-10 leading-relaxed">
          Self-healing diagnostics for multi-agent systems. Detect infinite loops,
          state corruption, and persona drift — then fix them automatically.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors"
          >
            Get Started Free
            <ArrowRight size={16} />
          </Link>
          <Link
            href="/demo"
            className="inline-flex items-center gap-2 px-6 py-3 border border-zinc-700 hover:border-zinc-600 text-zinc-300 hover:text-white font-medium rounded-lg transition-colors"
          >
            See Demo
          </Link>
        </div>

        <p className="mt-6 text-sm text-zinc-500">
          No credit card required. Works with LangGraph, CrewAI, AutoGen, n8n, and Dify.
        </p>
      </div>
    </section>
  )
}
