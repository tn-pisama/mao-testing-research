'use client'

import { useState } from 'react'
import Link from 'next/link'
import { ExternalLink } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  FAILURE_MODES,
  CATEGORY_TABS,
  severityColors,
  type FailureMode,
  type Category,
} from '@/lib/constants/failure-modes'

// ---------------------------------------------------------------------------
// Components
// ---------------------------------------------------------------------------

function AccuracyBar({ value, label }: { value: number; label: string }) {
  const pct = Math.round(value * 100)
  const color = value >= 0.8 ? 'bg-emerald-500' : value >= 0.7 ? 'bg-amber-500' : 'bg-zinc-500'
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-zinc-400 w-6">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-zinc-700 overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-zinc-300 w-10 text-right">{pct}%</span>
    </div>
  )
}

function FailureModeCard({ mode }: { mode: FailureMode }) {
  const Icon = mode.icon
  const sev = severityColors[mode.severity]

  return (
    <div className={`rounded-xl border p-6 ${sev.bg} ${sev.border}`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-zinc-800">
            <Icon size={20} className="text-blue-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-semibold text-white">{mode.title}</h3>
              {mode.mastId !== 'Ext' && (
                <span className="px-1.5 py-0.5 text-[10px] rounded bg-zinc-700 text-zinc-300">{mode.mastId}</span>
              )}
            </div>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={`text-xs uppercase ${sev.text}`}>{mode.severity}</span>
              <span className="text-zinc-600">|</span>
              <span className={`text-xs px-1.5 py-0.5 rounded ${mode.tier === 'Enterprise' ? 'bg-purple-500/20 text-purple-400' : 'bg-blue-500/20 text-blue-400'}`}>
                {mode.tier}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Description */}
      <p className="text-zinc-300 text-sm mb-4">{mode.description}</p>

      {/* Accuracy */}
      {mode.accuracy ? (
        <div className="mb-4 p-3 rounded-lg bg-zinc-800/50">
          <h4 className="text-xs font-medium text-zinc-400 mb-2">Detection Accuracy</h4>
          <div className="space-y-1">
            <AccuracyBar value={mode.accuracy.f1} label="F1" />
            {mode.accuracy.precision > 0 && <AccuracyBar value={mode.accuracy.precision} label="P" />}
            {mode.accuracy.recall > 0 && <AccuracyBar value={mode.accuracy.recall} label="R" />}
          </div>
        </div>
      ) : (
        <div className="mb-4 p-3 rounded-lg bg-zinc-800/50">
          <span className="text-xs text-zinc-500">Accuracy: Benchmarking in progress</span>
        </div>
      )}

      {/* Examples */}
      <div className="mb-4">
        <h4 className="text-sm font-medium text-zinc-400 mb-2">Real-World Examples</h4>
        <ul className="space-y-1">
          {mode.examples.map((ex, i) => (
            <li key={i} className="text-sm text-zinc-300 flex items-start gap-2">
              <span className="text-zinc-500 mt-0.5">&#x2022;</span>
              {ex}
            </li>
          ))}
        </ul>
      </div>

      {/* Detection Methods */}
      <div className="mb-4">
        <h4 className="text-sm font-medium text-zinc-400 mb-2">Detection Methods</h4>
        <div className="flex flex-wrap gap-2">
          {mode.methods.map((m) => (
            <span
              key={m.name}
              className="px-2 py-1 text-xs rounded bg-zinc-800 text-zinc-300"
              title={m.description}
            >
              {m.name}
            </span>
          ))}
        </div>
      </div>

      {/* Sub-types */}
      {mode.subTypes && mode.subTypes.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-zinc-400 mb-2">Sub-Types</h4>
          <div className="flex flex-wrap gap-1.5">
            {mode.subTypes.map((st) => (
              <span key={st} className="px-2 py-0.5 text-[11px] rounded-full bg-zinc-700/50 text-zinc-400">
                {st}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function SummaryTable() {
  const sorted = [...FAILURE_MODES]
    .filter((m) => m.accuracy !== null)
    .sort((a, b) => (b.accuracy?.f1 ?? 0) - (a.accuracy?.f1 ?? 0))

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-zinc-700">
            <th className="text-left py-2 px-3 text-zinc-400 font-medium">Detector</th>
            <th className="text-left py-2 px-3 text-zinc-400 font-medium">F1</th>
            <th className="text-left py-2 px-3 text-zinc-400 font-medium">Precision</th>
            <th className="text-left py-2 px-3 text-zinc-400 font-medium">Recall</th>
            <th className="text-left py-2 px-3 text-zinc-400 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((m) => {
            const f1 = m.accuracy!.f1
            const status = f1 >= 0.8 ? 'Production' : f1 >= 0.7 ? 'Beta' : 'Emerging'
            const statusColor = f1 >= 0.8 ? 'text-emerald-400' : f1 >= 0.7 ? 'text-amber-400' : 'text-zinc-400'
            return (
              <tr key={m.detectorKey} className="border-b border-zinc-800 hover:bg-zinc-800/30">
                <td className="py-2 px-3 text-white">{m.title}</td>
                <td className="py-2 px-3 text-zinc-300">{(f1 * 100).toFixed(1)}%</td>
                <td className="py-2 px-3 text-zinc-300">{m.accuracy!.precision > 0 ? `${(m.accuracy!.precision * 100).toFixed(1)}%` : '—'}</td>
                <td className="py-2 px-3 text-zinc-300">{m.accuracy!.recall > 0 ? `${(m.accuracy!.recall * 100).toFixed(1)}%` : '—'}</td>
                <td className={`py-2 px-3 text-xs font-medium ${statusColor}`}>{status}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function FailureModesPage() {
  const [activeTab, setActiveTab] = useState<Category>('planning')

  const modesInTab = FAILURE_MODES.filter((m) => m.category === activeTab)
  const productionCount = FAILURE_MODES.filter((m) => m.accuracy && m.accuracy.f1 >= 0.8).length
  const betaCount = FAILURE_MODES.filter((m) => m.accuracy && m.accuracy.f1 >= 0.7 && m.accuracy.f1 < 0.8).length
  const enterpriseCount = FAILURE_MODES.filter((m) => m.tier === 'Enterprise').length

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-4">Failure Mode Reference</h1>
        <p className="text-lg text-zinc-300 mb-4">
          Comprehensive reference for all failure mode detectors. Based on the{' '}
          <a
            href="https://arxiv.org/abs/2503.13657"
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-400 hover:underline inline-flex items-center gap-1"
          >
            MAST Taxonomy <ExternalLink size={14} />
          </a>{' '}
          (NeurIPS 2025) with enterprise extensions.
        </p>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-4 gap-3 mb-8">
        <div className="p-3 rounded-xl bg-zinc-800/50 border border-zinc-700 text-center">
          <div className="text-2xl font-bold text-white">{FAILURE_MODES.length}</div>
          <div className="text-xs text-zinc-400">Total Detectors</div>
        </div>
        <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-center">
          <div className="text-2xl font-bold text-emerald-400">{productionCount}</div>
          <div className="text-xs text-zinc-400">Production</div>
        </div>
        <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-center">
          <div className="text-2xl font-bold text-amber-400">{betaCount}</div>
          <div className="text-xs text-zinc-400">Beta</div>
        </div>
        <div className="p-3 rounded-xl bg-purple-500/10 border border-purple-500/30 text-center">
          <div className="text-2xl font-bold text-purple-400">{enterpriseCount}</div>
          <div className="text-xs text-zinc-400">Enterprise</div>
        </div>
      </div>

      {/* Category Tabs */}
      <div className="flex gap-1 mb-2 border-b border-zinc-700 overflow-x-auto">
        {CATEGORY_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              'px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-colors border-b-2 -mb-px',
              activeTab === tab.key
                ? 'border-blue-400 text-blue-400'
                : 'border-transparent text-zinc-400 hover:text-white hover:border-zinc-500'
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Category Description */}
      <p className="text-sm text-zinc-400 mb-6">
        {CATEGORY_TABS.find((t) => t.key === activeTab)?.description}
      </p>

      {/* Failure Mode Cards */}
      <div className="space-y-6 mb-12">
        {modesInTab.map((mode) => (
          <FailureModeCard key={mode.detectorKey} mode={mode} />
        ))}
      </div>

      {/* Accuracy Summary Table */}
      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Accuracy Summary</h2>
        <p className="text-sm text-zinc-300 mb-4">
          All benchmarked detectors ranked by F1 score. Production (F1 &ge; 80%), Beta (70-79%), Emerging (&lt;70%).
        </p>
        <div className="rounded-xl border border-zinc-700 bg-zinc-800/30 p-4">
          <SummaryTable />
        </div>
      </section>

      {/* Tiered Detection */}
      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Tiered Detection Architecture</h2>
        <p className="text-sm text-zinc-300 mb-4">
          PISAMA uses a tiered escalation system to balance cost and accuracy. Target: $0.05/trace average.
        </p>
        <div className="space-y-2">
          {[
            { tier: 'Tier 1', method: 'Hash-based detection', cost: '<$0.001', desc: 'Always -- fastest, cheapest' },
            { tier: 'Tier 2', method: 'State delta analysis', cost: '$0.005-0.01', desc: 'When Tier 1 confidence is low' },
            { tier: 'Tier 3', method: 'Embedding/ML detection', cost: '$0.01-0.02', desc: 'When Tier 2 is inconclusive' },
            { tier: 'Tier 4', method: 'LLM-as-Judge', cost: '$0.05-0.10', desc: 'Gray zone cases requiring reasoning' },
            { tier: 'Tier 5', method: 'Human review', cost: 'Variable', desc: 'When all automated tiers are uncertain' },
          ].map((t) => (
            <div key={t.tier} className="flex items-center gap-3 p-3 rounded-lg bg-zinc-800/50">
              <span className="text-xs text-blue-400 w-12">{t.tier}</span>
              <span className="text-sm text-white flex-1">{t.method}</span>
              <span className="text-xs text-zinc-400 w-24 text-right">{t.cost}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Cross-link */}
      <section className="bg-zinc-800/50 rounded-xl border border-zinc-700 p-6">
        <p className="text-sm text-zinc-300">
          See also:{' '}
          <Link href="/docs/detections" className="text-blue-400 hover:underline">
            Detections overview
          </Link>{' '}
          for interpreting detection results and validation guidelines, or the{' '}
          <Link href="/docs/methodology" className="text-blue-400 hover:underline">
            Methodology
          </Link>{' '}
          page for the research foundation.
        </p>
      </section>
    </div>
  )
}
