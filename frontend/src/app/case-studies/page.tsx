'use client'

import { useState } from 'react'
import {
  Users, TrendingUp, Clock, Shield, ChevronRight,
  CheckCircle, AlertTriangle, Zap, BarChart3, Quote,
  Terminal, ExternalLink, ArrowRight
} from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import Link from 'next/link'

interface CaseStudy {
  id: string
  title: string
  organization: string
  useCase: string
  framework: string
  duration: string
  summary: string
  metrics: {
    label: string
    before: string
    after: string
    improvement: string
  }[]
  failuresCaught: {
    code: string
    name: string
    count: number
  }[]
  quote?: {
    text: string
    author: string
    role: string
  }
  featured: boolean
}

const CASE_STUDIES: CaseStudy[] = [
  {
    id: 'internal-dogfooding',
    title: 'Internal Dogfooding',
    organization: 'PISAMA Development Team',
    useCase: 'Claude Code agent development and debugging',
    framework: 'Claude Code',
    duration: '6 months',
    summary: 'The PISAMA team used its own detection and self-healing capabilities during development, uncovering 47 agent failures and preventing 12 infinite loops from reaching production.',
    metrics: [
      { label: 'Loop detection time', before: 'Minutes', after: '8.3 sec', improvement: '95%+' },
      { label: 'Sessions lost to loops', before: '2-3/week', after: '0', improvement: '100%' },
      { label: 'Debug time per session', before: '30+ min', after: '2 min', improvement: '93%' },
    ],
    failuresCaught: [
      { code: 'F1', name: 'Exact Loop', count: 18 },
      { code: 'F3', name: 'Semantic Loop', count: 9 },
      { code: 'F6', name: 'Task Derailment', count: 7 },
      { code: 'F11', name: 'Coordination Failure', count: 5 },
    ],
    quote: {
      text: "Before PISAMA, I'd come back from lunch to find my agent had burned through $50 in tokens doing nothing. Now I get an alert within seconds of a loop starting.",
      author: 'Development Team',
      role: 'PISAMA',
    },
    featured: true,
  },
]

const UPCOMING_STUDIES = [
  {
    title: 'Claude Code Beta Users',
    focus: 'Early adopter detection accuracy and developer experience',
    status: 'In Progress',
  },
  {
    title: 'n8n Workflow Integration',
    focus: 'Automated workflow failure prevention',
    status: 'Planned',
  },
]

function MetricCard({ label, before, after, improvement }: {
  label: string
  before: string
  after: string
  improvement: string
}) {
  return (
    <div className="bg-slate-900/50 rounded-lg p-4">
      <div className="text-xs text-slate-400 mb-2">{label}</div>
      <div className="flex items-center gap-2 mb-1">
        <span className="text-slate-500 line-through text-sm">{before}</span>
        <ArrowRight size={12} className="text-slate-600" />
        <span className="text-emerald-400 font-semibold">{after}</span>
      </div>
      <div className="text-xs text-emerald-400">
        {improvement} improvement
      </div>
    </div>
  )
}

function FailureBadge({ code, name, count }: { code: string; name: string; count: number }) {
  return (
    <div className="flex items-center justify-between py-2 px-3 bg-slate-900/30 rounded-lg">
      <div className="flex items-center gap-2">
        <span className="text-amber-400 text-xs">{code}</span>
        <span className="text-slate-300 text-sm">{name}</span>
      </div>
      <span className="text-slate-400 text-xs">{count} caught</span>
    </div>
  )
}

function CaseStudyCard({ study }: { study: CaseStudy }) {
  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
      {/* Header */}
      <div className="p-6 border-b border-slate-700">
        <div className="flex items-start justify-between mb-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="px-2 py-0.5 text-xs rounded bg-indigo-500/20 text-indigo-300">
                {study.framework}
              </span>
              <span className="text-xs text-slate-500">{study.duration}</span>
            </div>
            <h3 className="text-xl font-bold text-white">{study.title}</h3>
            <p className="text-sm text-slate-400">{study.organization}</p>
          </div>
          {study.featured && (
            <span className="px-2 py-1 text-xs rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
              Featured
            </span>
          )}
        </div>
        <p className="text-slate-300 text-sm">{study.summary}</p>
      </div>

      {/* Metrics */}
      <div className="p-6 border-b border-slate-700">
        <h4 className="text-sm font-medium text-slate-300 mb-4 flex items-center gap-2">
          <TrendingUp size={16} className="text-emerald-400" />
          Impact Metrics
        </h4>
        <div className="grid grid-cols-3 gap-3">
          {study.metrics.map((metric, i) => (
            <MetricCard key={i} {...metric} />
          ))}
        </div>
      </div>

      {/* Failures Caught */}
      <div className="p-6 border-b border-slate-700">
        <h4 className="text-sm font-medium text-slate-300 mb-4 flex items-center gap-2">
          <Shield size={16} className="text-amber-400" />
          Failures Detected
        </h4>
        <div className="space-y-2">
          {study.failuresCaught.map((failure, i) => (
            <FailureBadge key={i} {...failure} />
          ))}
        </div>
      </div>

      {/* Quote */}
      {study.quote && (
        <div className="p-6 bg-slate-900/30">
          <div className="flex gap-3">
            <Quote size={20} className="text-slate-600 flex-shrink-0 mt-1" />
            <div>
              <p className="text-slate-300 text-sm italic mb-2">"{study.quote.text}"</p>
              <p className="text-xs text-slate-500">
                — {study.quote.author}, {study.quote.role}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function CaseStudiesPage() {
  return (
    <Layout>
      <div className="p-6 max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-indigo-600/20 rounded-lg">
              <Users className="w-6 h-6 text-indigo-400" />
            </div>
            <h1 className="text-2xl font-bold text-white">Case Studies</h1>
          </div>
          <p className="text-slate-400">
            Real-world results from teams using PISAMA to detect and prevent agent failures
          </p>
        </div>

        {/* Stats Overview */}
        <div className="grid md:grid-cols-4 gap-4 mb-8">
          <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
            <div className="flex items-center gap-2 mb-2">
              <CheckCircle className="text-emerald-400" size={20} />
              <span className="text-slate-400 text-sm">Failures Caught</span>
            </div>
            <div className="text-3xl font-bold text-white">47</div>
            <div className="text-xs text-slate-500 mt-1">Across all case studies</div>
          </div>

          <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
            <div className="flex items-center gap-2 mb-2">
              <Clock className="text-blue-400" size={20} />
              <span className="text-slate-400 text-sm">Avg Detection Time</span>
            </div>
            <div className="text-3xl font-bold text-white">8.3s</div>
            <div className="text-xs text-slate-500 mt-1">From loop start</div>
          </div>

          <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
            <div className="flex items-center gap-2 mb-2">
              <Zap className="text-amber-400" size={20} />
              <span className="text-slate-400 text-sm">Auto-Healed</span>
            </div>
            <div className="text-3xl font-bold text-white">68%</div>
            <div className="text-xs text-slate-500 mt-1">Without intervention</div>
          </div>

          <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
            <div className="flex items-center gap-2 mb-2">
              <BarChart3 className="text-purple-400" size={20} />
              <span className="text-slate-400 text-sm">Debug Time Saved</span>
            </div>
            <div className="text-3xl font-bold text-white">93%</div>
            <div className="text-xs text-slate-500 mt-1">Reduction in debugging</div>
          </div>
        </div>

        {/* Featured Case Studies */}
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-white mb-4">Featured Case Studies</h2>
          <div className="grid gap-6">
            {CASE_STUDIES.filter(s => s.featured).map((study) => (
              <CaseStudyCard key={study.id} study={study} />
            ))}
          </div>
        </div>

        {/* Upcoming */}
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-white mb-4">Coming Soon</h2>
          <div className="grid md:grid-cols-2 gap-4">
            {UPCOMING_STUDIES.map((study, i) => (
              <div key={i} className="bg-slate-800/50 rounded-xl p-5 border border-slate-700 border-dashed">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-white font-medium">{study.title}</h3>
                  <span className={`px-2 py-0.5 text-xs rounded ${
                    study.status === 'In Progress'
                      ? 'bg-blue-500/20 text-blue-300'
                      : 'bg-slate-600/50 text-slate-400'
                  }`}>
                    {study.status}
                  </span>
                </div>
                <p className="text-sm text-slate-400">{study.focus}</p>
              </div>
            ))}
          </div>
        </div>

        {/* CTA */}
        <div className="bg-gradient-to-r from-indigo-600/20 to-purple-600/20 rounded-xl p-8 border border-indigo-500/30 text-center">
          <h3 className="text-xl font-bold text-white mb-2">Ready to see results?</h3>
          <p className="text-slate-300 mb-6 max-w-md mx-auto">
            Install PISAMA in under a minute and start detecting agent failures immediately.
          </p>
          <div className="flex items-center justify-center gap-4">
            <div className="bg-slate-900 rounded-lg px-4 py-2 font-mono text-sm text-emerald-400 flex items-center gap-2">
              <Terminal size={16} />
              pip install pisama-claude-code
            </div>
            <Link href="/docs/getting-started" className="flex items-center gap-2 text-indigo-400 hover:text-indigo-300 text-sm">
              View docs
              <ExternalLink size={14} />
            </Link>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-6 text-center text-xs text-slate-500">
          Have a success story? <a href="mailto:hello@pisama.dev" className="text-indigo-400 hover:underline">Share it with us</a>
        </div>
      </div>
    </Layout>
  )
}
