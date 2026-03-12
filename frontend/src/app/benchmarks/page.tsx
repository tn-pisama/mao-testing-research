'use client'

import { useState } from 'react'
import {
  BarChart3, CheckCircle, AlertTriangle, Info,
  TrendingUp, Target, Zap, Shield, FileText,
  ChevronDown, ChevronUp
} from 'lucide-react'
import { Layout } from '@/components/common/Layout'

// Benchmark data from DETECTION_REPORT.md
const OVERALL_STATS = {
  detectionRate: 82.4,
  totalTraces: 1300,
  detectedTraces: 1071,
  failureModes: 16,
  lastUpdated: '2026-01-05',
}

interface FailureMode {
  code: string
  name: string
  category: 'content' | 'structural' | 'rag'
  rate: number | null
  detected: number
  total: number
  tier: 1 | 2 | 3
  description: string
  improvement?: { before: number; after: number }
}

const FAILURE_MODES: FailureMode[] = [
  // Tier 1: High Detection (>95%)
  { code: 'F1', name: 'Specification Mismatch', category: 'content', rate: 98, detected: 49, total: 50, tier: 1, description: 'Output doesn\'t match what was requested', improvement: { before: 0, after: 98 } },
  { code: 'F2', name: 'Poor Task Decomposition', category: 'structural', rate: 100, detected: 50, total: 50, tier: 1, description: 'Tasks broken down incorrectly', improvement: { before: 10, after: 100 } },
  { code: 'F5', name: 'Flawed Workflow Design', category: 'structural', rate: 100, detected: 150, total: 150, tier: 1, description: 'Workflow has structural issues' },
  { code: 'F6', name: 'Task Derailment', category: 'content', rate: 100, detected: 50, total: 50, tier: 1, description: 'Agent goes off-topic' },
  { code: 'F7', name: 'Context Neglect', category: 'content', rate: 100, detected: 50, total: 50, tier: 1, description: 'Agent ignores provided context', improvement: { before: 10, after: 100 } },
  { code: 'F8', name: 'Information Withholding', category: 'content', rate: 100, detected: 50, total: 50, tier: 1, description: 'Agent omits critical info' },
  { code: 'F11', name: 'Coordination Failure', category: 'structural', rate: 100, detected: 150, total: 150, tier: 1, description: 'Agents fail to coordinate' },
  { code: 'F13', name: 'Quality Gate Bypass', category: 'content', rate: 96, detected: 48, total: 50, tier: 1, description: 'Skips quality checks' },

  // Tier 2: Good Detection (60-95%)
  { code: 'F14', name: 'Completion Misjudgment', category: 'content', rate: 84, detected: 42, total: 50, tier: 2, description: 'Declares done when incomplete', improvement: { before: 6, after: 84 } },
  { code: 'F3', name: 'Resource Misallocation', category: 'structural', rate: 66.7, detected: 100, total: 150, tier: 2, description: 'Compute/time allocated poorly' },
  { code: 'F4', name: 'Inadequate Tool Provision', category: 'structural', rate: 66.7, detected: 100, total: 150, tier: 2, description: 'Wrong tools used for task' },
  { code: 'F9', name: 'Role Usurpation', category: 'structural', rate: 66.7, detected: 100, total: 150, tier: 2, description: 'Agent exceeds its role boundaries' },
  { code: 'F12', name: 'Output Validation Failure', category: 'structural', rate: 66.7, detected: 100, total: 150, tier: 2, description: 'Output not validated properly' },
  { code: 'F10', name: 'Communication Breakdown', category: 'content', rate: 64, detected: 32, total: 50, tier: 2, description: 'Inter-agent comms fail' },

  // Tier 3: RAG/Grounding
  { code: 'F15', name: 'Grounding Failure', category: 'rag', rate: null, detected: 0, total: 0, tier: 3, description: 'Claims not supported by sources' },
  { code: 'F16', name: 'Retrieval Quality Failure', category: 'rag', rate: null, detected: 0, total: 0, tier: 3, description: 'Retrieves wrong/irrelevant docs' },
]

const METHODOLOGY = {
  datasetSize: '207MB',
  traceCount: 20575,
  sources: ['HuggingFace', 'GitHub', 'Anthropic', 'Research Papers'],
  frameworks: ['LangChain', 'LangGraph', 'AutoGen', 'CrewAI', 'OpenAI', 'Anthropic'],
  detectionApproach: [
    'Pattern matching for structural failures',
    'Semantic analysis using sentence embeddings',
    'Intent parsing for specification alignment',
    'Marker detection for completion tracking',
  ],
}

function ProgressBar({ value, max = 100, color = 'indigo' }: { value: number; max?: number; color?: string }) {
  const percentage = (value / max) * 100
  const colorClasses = {
    indigo: 'bg-indigo-500',
    emerald: 'bg-emerald-500',
    amber: 'bg-amber-500',
    red: 'bg-red-500',
  }

  return (
    <div className="w-full bg-zinc-700 rounded-full h-2">
      <div
        className={`h-2 rounded-full ${colorClasses[color as keyof typeof colorClasses] || colorClasses.indigo}`}
        style={{ width: `${percentage}%` }}
      />
    </div>
  )
}

function _TierBadge({ tier }: { tier: 1 | 2 | 3 }) {
  const styles = {
    1: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    2: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    3: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30',
  }
  const labels = {
    1: 'Tier 1: >95%',
    2: 'Tier 2: 60-95%',
    3: 'Tier 3: New',
  }

  return (
    <span className={`px-2 py-0.5 text-xs rounded border ${styles[tier]}`}>
      {labels[tier]}
    </span>
  )
}

function CategoryBadge({ category }: { category: 'content' | 'structural' | 'rag' }) {
  const styles = {
    content: 'bg-blue-500/20 text-blue-400',
    structural: 'bg-purple-500/20 text-purple-400',
    rag: 'bg-orange-500/20 text-orange-400',
  }
  const labels = {
    content: 'Content',
    structural: 'Structural',
    rag: 'RAG',
  }

  return (
    <span className={`px-2 py-0.5 text-xs rounded ${styles[category]}`}>
      {labels[category]}
    </span>
  )
}

export default function BenchmarksPage() {
  const [_expandedMode, _setExpandedMode] = useState<string | null>(null)
  const [showMethodology, setShowMethodology] = useState(false)

  const tier1Modes = FAILURE_MODES.filter(m => m.tier === 1)
  const tier2Modes = FAILURE_MODES.filter(m => m.tier === 2)
  const tier3Modes = FAILURE_MODES.filter(m => m.tier === 3)

  return (
    <Layout>
      <div className="p-6 max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-emerald-600/20 rounded-lg">
              <Target className="w-6 h-6 text-emerald-400" />
            </div>
            <h1 className="text-2xl font-bold text-white">Detection Benchmarks</h1>
          </div>
          <p className="text-zinc-400">
            Transparent accuracy metrics for MAST failure mode detection
          </p>
        </div>

        {/* Overall Stats */}
        <div className="grid md:grid-cols-4 gap-4 mb-8">
          <div className="bg-zinc-800 rounded-xl p-5 border border-zinc-700">
            <div className="flex items-center gap-2 mb-2">
              <BarChart3 className="text-emerald-400" size={20} />
              <span className="text-zinc-400 text-sm">Detection Rate</span>
            </div>
            <div className="text-3xl font-bold text-white">{OVERALL_STATS.detectionRate}%</div>
            <div className="text-xs text-zinc-500 mt-1">
              {OVERALL_STATS.detectedTraces.toLocaleString()}/{OVERALL_STATS.totalTraces.toLocaleString()} traces
            </div>
          </div>

          <div className="bg-zinc-800 rounded-xl p-5 border border-zinc-700">
            <div className="flex items-center gap-2 mb-2">
              <Shield className="text-indigo-400" size={20} />
              <span className="text-zinc-400 text-sm">Failure Modes</span>
            </div>
            <div className="text-3xl font-bold text-white">{OVERALL_STATS.failureModes}</div>
            <div className="text-xs text-zinc-500 mt-1">F1-F16 MAST taxonomy</div>
          </div>

          <div className="bg-zinc-800 rounded-xl p-5 border border-zinc-700">
            <div className="flex items-center gap-2 mb-2">
              <Zap className="text-amber-400" size={20} />
              <span className="text-zinc-400 text-sm">High Confidence</span>
            </div>
            <div className="text-3xl font-bold text-white">8</div>
            <div className="text-xs text-zinc-500 mt-1">Modes with &gt;95% detection</div>
          </div>

          <div className="bg-zinc-800 rounded-xl p-5 border border-zinc-700">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="text-blue-400" size={20} />
              <span className="text-zinc-400 text-sm">Improvement</span>
            </div>
            <div className="text-3xl font-bold text-white">+13.7%</div>
            <div className="text-xs text-zinc-500 mt-1">From 68.7% baseline</div>
          </div>
        </div>

        {/* Tier 1: High Detection */}
        <div className="mb-6">
          <div className="flex items-center gap-3 mb-4">
            <CheckCircle className="text-emerald-400" size={20} />
            <h2 className="text-lg font-semibold text-white">Tier 1: High Detection (&gt;95%)</h2>
            <span className="text-xs text-zinc-500">{tier1Modes.length} modes</span>
          </div>
          <div className="bg-zinc-800 rounded-xl border border-zinc-700 overflow-hidden">
            <table className="w-full">
              <thead className="bg-zinc-900/50">
                <tr>
                  <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">Mode</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">Category</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">Detection Rate</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">Sample</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-700">
                {tier1Modes.map((mode) => (
                  <tr key={mode.code} className="hover:bg-zinc-700/30">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className="text-emerald-400 text-sm">{mode.code}</span>
                        <span className="text-white text-sm">{mode.name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <CategoryBadge category={mode.category} />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <span className="text-emerald-400 font-semibold">{mode.rate}%</span>
                        <div className="w-24">
                          <ProgressBar value={mode.rate || 0} color="emerald" />
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-zinc-400 text-sm">
                      {mode.detected}/{mode.total}
                    </td>
                    <td className="px-4 py-3">
                      {mode.improvement && (
                        <span className="text-xs text-emerald-400">
                          +{mode.improvement.after - mode.improvement.before}%
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Tier 2: Good Detection */}
        <div className="mb-6">
          <div className="flex items-center gap-3 mb-4">
            <AlertTriangle className="text-amber-400" size={20} />
            <h2 className="text-lg font-semibold text-white">Tier 2: Good Detection (60-95%)</h2>
            <span className="text-xs text-zinc-500">{tier2Modes.length} modes</span>
          </div>
          <div className="bg-zinc-800 rounded-xl border border-zinc-700 overflow-hidden">
            <table className="w-full">
              <thead className="bg-zinc-900/50">
                <tr>
                  <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">Mode</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">Category</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">Detection Rate</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">Sample</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-700">
                {tier2Modes.map((mode) => (
                  <tr key={mode.code} className="hover:bg-zinc-700/30">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className="text-amber-400 text-sm">{mode.code}</span>
                        <span className="text-white text-sm">{mode.name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <CategoryBadge category={mode.category} />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <span className="text-amber-400 font-semibold">{mode.rate}%</span>
                        <div className="w-24">
                          <ProgressBar value={mode.rate || 0} color="amber" />
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-zinc-400 text-sm">
                      {mode.detected}/{mode.total}
                    </td>
                    <td className="px-4 py-3">
                      {mode.improvement && (
                        <span className="text-xs text-emerald-400">
                          +{mode.improvement.after - mode.improvement.before}%
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Tier 3: RAG/Grounding */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-4">
            <Info className="text-zinc-400" size={20} />
            <h2 className="text-lg font-semibold text-white">Tier 3: RAG/Grounding (New)</h2>
            <span className="text-xs text-zinc-500">{tier3Modes.length} modes</span>
          </div>
          <div className="bg-zinc-800 rounded-xl border border-zinc-700 overflow-hidden">
            <table className="w-full">
              <thead className="bg-zinc-900/50">
                <tr>
                  <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">Mode</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">Category</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">Status</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400">Description</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-700">
                {tier3Modes.map((mode) => (
                  <tr key={mode.code} className="hover:bg-zinc-700/30">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className="text-zinc-400 text-sm">{mode.code}</span>
                        <span className="text-white text-sm">{mode.name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <CategoryBadge category={mode.category} />
                    </td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 text-xs rounded bg-zinc-600/50 text-zinc-300">
                        Evaluation Pending
                      </span>
                    </td>
                    <td className="px-4 py-3 text-zinc-400 text-sm">
                      {mode.description}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Methodology */}
        <div className="bg-zinc-800 rounded-xl border border-zinc-700 overflow-hidden">
          <button
            onClick={() => setShowMethodology(!showMethodology)}
            className="w-full flex items-center justify-between p-4 text-left hover:bg-zinc-700/30"
          >
            <div className="flex items-center gap-2">
              <FileText className="text-indigo-400" size={20} />
              <h2 className="text-lg font-semibold text-white">Methodology & Transparency</h2>
            </div>
            {showMethodology ? (
              <ChevronUp className="text-zinc-400" size={20} />
            ) : (
              <ChevronDown className="text-zinc-400" size={20} />
            )}
          </button>

          {showMethodology && (
            <div className="p-4 pt-0 border-t border-zinc-700">
              <div className="grid md:grid-cols-2 gap-6 mt-4">
                <div>
                  <h3 className="text-sm font-medium text-zinc-300 mb-3">Dataset</h3>
                  <ul className="space-y-2 text-sm text-zinc-400">
                    <li className="flex justify-between">
                      <span>Total Size</span>
                      <span className="text-white">{METHODOLOGY.datasetSize}</span>
                    </li>
                    <li className="flex justify-between">
                      <span>Trace Count</span>
                      <span className="text-white">{METHODOLOGY.traceCount.toLocaleString()}</span>
                    </li>
                    <li className="flex justify-between">
                      <span>Sources</span>
                      <span className="text-white">{METHODOLOGY.sources.length}</span>
                    </li>
                  </ul>
                  <div className="mt-3">
                    <span className="text-xs text-zinc-500">Data Sources:</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {METHODOLOGY.sources.map((source) => (
                        <span key={source} className="px-2 py-0.5 text-xs bg-zinc-700 text-zinc-300 rounded">
                          {source}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                <div>
                  <h3 className="text-sm font-medium text-zinc-300 mb-3">Detection Approach</h3>
                  <ul className="space-y-2">
                    {METHODOLOGY.detectionApproach.map((approach, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-zinc-400">
                        <CheckCircle className="text-emerald-400 mt-0.5 flex-shrink-0" size={14} />
                        {approach}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-zinc-700">
                <h3 className="text-sm font-medium text-zinc-300 mb-3">Framework Coverage</h3>
                <div className="flex flex-wrap gap-2">
                  {METHODOLOGY.frameworks.map((framework) => (
                    <span key={framework} className="px-3 py-1 text-sm bg-indigo-500/20 text-indigo-300 rounded-lg">
                      {framework}
                    </span>
                  ))}
                </div>
              </div>

              <div className="mt-6 p-4 bg-zinc-900/50 rounded-lg">
                <div className="flex items-start gap-2">
                  <Info className="text-blue-400 mt-0.5 flex-shrink-0" size={16} />
                  <div className="text-sm text-zinc-400">
                    <p className="mb-2">
                      <strong className="text-zinc-300">No mock data:</strong> All traces are sourced from real-world
                      datasets including HuggingFace agent traces, GitHub repositories, and published research.
                    </p>
                    <p>
                      <strong className="text-zinc-300">Reproducibility:</strong> Full evaluation scripts available at{' '}
                      <code className="px-1 bg-zinc-800 rounded text-xs">/benchmarks/evaluation/</code>
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Improvement History */}
        <div className="mt-6 bg-zinc-800/50 rounded-xl border border-zinc-700 p-4">
          <h3 className="text-sm font-medium text-zinc-300 mb-4">Key Improvements</h3>
          <div className="grid md:grid-cols-4 gap-4">
            {FAILURE_MODES.filter(m => m.improvement).map((mode) => (
              <div key={mode.code} className="p-3 bg-zinc-900/50 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-emerald-400 text-xs">{mode.code}</span>
                  <span className="text-white text-sm">{mode.name}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-zinc-500 text-xs">{mode.improvement?.before}%</span>
                  <TrendingUp className="text-emerald-400" size={12} />
                  <span className="text-emerald-400 text-xs font-semibold">{mode.improvement?.after}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="mt-6 text-center text-xs text-zinc-500">
          Last updated: {OVERALL_STATS.lastUpdated} | Evaluation runs automatically on new detector versions
        </div>
      </div>
    </Layout>
  )
}
