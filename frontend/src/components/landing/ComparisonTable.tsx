'use client'

import { Fragment } from 'react'
import { Check, X } from 'lucide-react'

export function ComparisonTable() {
  const features = [
    {
      category: 'Failure Detection',
      rows: [
        { name: 'Infinite Loop Detection', pisama: true, langsmith: false, langfuse: false, agentops: 'partial' },
        { name: 'State Corruption Detection', pisama: true, langsmith: false, langfuse: false, agentops: false },
        { name: 'Persona Drift Detection', pisama: true, langsmith: false, langfuse: false, agentops: false },
        { name: 'Deadlock Detection', pisama: true, langsmith: false, langfuse: false, agentops: true },
      ],
    },
    {
      category: 'Remediation',
      rows: [
        { name: 'AI-Powered Fix Suggestions', pisama: true, langsmith: false, langfuse: false, agentops: false },
        { name: 'Self-Healing (Coming Soon)', pisama: 'soon', langsmith: false, langfuse: false, agentops: false },
        { name: 'Root Cause Analysis', pisama: true, langsmith: 'partial', langfuse: 'partial', agentops: true },
      ],
    },
    {
      category: 'Framework Support',
      rows: [
        { name: 'LangGraph', pisama: true, langsmith: true, langfuse: true, agentops: 'partial' },
        { name: 'CrewAI', pisama: true, langsmith: 'partial', langfuse: true, agentops: true },
        { name: 'AutoGen', pisama: true, langsmith: 'partial', langfuse: true, agentops: true },
        { name: 'Custom Frameworks', pisama: true, langsmith: 'partial', langfuse: true, agentops: 'partial' },
      ],
    },
    {
      category: 'Deployment & Pricing',
      rows: [
        { name: 'Open Source', pisama: true, langsmith: false, langfuse: true, agentops: false },
        { name: 'Self-Hosted', pisama: true, langsmith: 'paid', langfuse: true, agentops: false },
        { name: 'Free Tier', pisama: '10K spans', langsmith: '5K traces', langfuse: '50K events', agentops: '1K agents' },
      ],
    },
  ]

  const renderCell = (value: boolean | string) => {
    if (value === true) {
      return <Check className="w-5 h-5 text-green-400 mx-auto" />
    }
    if (value === false) {
      return <X className="w-5 h-5 text-zinc-600 mx-auto" />
    }
    if (value === 'partial') {
      return <span className="text-amber-400 text-sm">⚠️</span>
    }
    if (value === 'paid') {
      return <span className="text-amber-400 text-xs">💰 Paid</span>
    }
    if (value === 'soon') {
      return <span className="text-sky-400 text-xs">Coming</span>
    }
    return <span className="text-zinc-400 text-xs">{value}</span>
  }

  return (
    <section className="py-20 px-4 bg-zinc-900/30">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
            How PISAMA Compares
          </h2>
          <p className="text-zinc-400 text-lg">
            The only platform built specifically for multi-agent failure detection
          </p>
        </div>

        {/* Desktop Table */}
        <div className="hidden lg:block overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b border-zinc-700">
                <th className="text-left py-4 px-4 text-zinc-400 font-medium">Feature</th>
                <th className="text-center py-4 px-4">
                  <div className="text-white font-semibold mb-1">PISAMA</div>
                  <div className="text-sky-400 text-xs">You are here</div>
                </th>
                <th className="text-center py-4 px-4 text-zinc-300 font-medium">LangSmith</th>
                <th className="text-center py-4 px-4 text-zinc-300 font-medium">Langfuse</th>
                <th className="text-center py-4 px-4 text-zinc-300 font-medium">AgentOps</th>
              </tr>
            </thead>
            <tbody>
              {features.map((category, catIndex) => (
                <Fragment key={`cat-${catIndex}`}>
                  <tr>
                    <td colSpan={5} className="py-4 px-4">
                      <div className="text-white font-semibold text-sm uppercase tracking-wider">
                        {category.category}
                      </div>
                    </td>
                  </tr>
                  {category.rows.map((row, rowIndex) => (
                    <tr
                      key={`${catIndex}-${rowIndex}`}
                      className="border-b border-zinc-800 hover:bg-zinc-800/30"
                    >
                      <td className="py-3 px-4 text-zinc-300">{row.name}</td>
                      <td className="py-3 px-4 bg-sky-500/10">{renderCell(row.pisama)}</td>
                      <td className="py-3 px-4">{renderCell(row.langsmith)}</td>
                      <td className="py-3 px-4">{renderCell(row.langfuse)}</td>
                      <td className="py-3 px-4">{renderCell(row.agentops)}</td>
                    </tr>
                  ))}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>

        {/* Mobile Cards */}
        <div className="lg:hidden space-y-6">
          {features.map((category, catIndex) => (
            <div key={catIndex} className="bg-zinc-800/50 rounded-xl p-6 border border-zinc-700">
              <h3 className="text-white font-semibold mb-4">{category.category}</h3>
              <div className="space-y-3">
                {category.rows.map((row, rowIndex) => (
                  <div key={rowIndex} className="flex justify-between items-center">
                    <span className="text-zinc-300 text-sm">{row.name}</span>
                    <div className="flex gap-2 items-center">
                      <span className="text-xs text-zinc-500">PISAMA:</span>
                      {renderCell(row.pisama)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Legend */}
        <div className="mt-8 flex flex-wrap gap-6 justify-center text-sm text-zinc-400">
          <div className="flex items-center gap-2">
            <Check className="w-4 h-4 text-green-400" />
            <span>Full Support</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-amber-400">⚠️</span>
            <span>Partial Support</span>
          </div>
          <div className="flex items-center gap-2">
            <X className="w-4 h-4 text-zinc-600" />
            <span>Not Available</span>
          </div>
        </div>
      </div>
    </section>
  )
}
