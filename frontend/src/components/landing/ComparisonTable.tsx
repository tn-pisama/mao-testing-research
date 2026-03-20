'use client'

import { Fragment } from 'react'
import { Check, X } from 'lucide-react'

export function ComparisonTable() {
  const features = [
    {
      category: 'Failure Detection',
      rows: [
        { name: '42 failure mode detectors', pisama: true, others: false },
        { name: 'Loop, corruption, drift, deadlock', pisama: true, others: false },
        { name: 'Convergence & metric tracking', pisama: true, others: false },
        { name: 'Prompt injection detection', pisama: true, others: false },
      ],
    },
    {
      category: 'Remediation',
      rows: [
        { name: 'AI-powered fix suggestions', pisama: true, others: false },
        { name: 'Self-healing with rollback', pisama: true, others: false },
        { name: 'Root cause analysis', pisama: true, others: 'partial' },
      ],
    },
    {
      category: 'Framework Support',
      rows: [
        { name: 'LangGraph', pisama: true, others: 'partial' },
        { name: 'CrewAI / AutoGen', pisama: true, others: 'partial' },
        { name: 'n8n / Dify / OpenClaw', pisama: true, others: false },
        { name: 'Any framework via OTEL', pisama: true, others: 'partial' },
      ],
    },
    {
      category: 'Platform',
      rows: [
        { name: 'Open source (MIT)', pisama: true, others: 'partial' },
        { name: 'Self-hosted option', pisama: true, others: 'partial' },
        { name: 'Production-grade (31 detectors F1 > 0.70)', pisama: true, others: false },
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
      return <span className="text-amber-400 text-sm block text-center">Varies</span>
    }
    return <span className="text-zinc-400 text-xs">{value}</span>
  }

  return (
    <section className="py-14 px-4 bg-zinc-900/30">
      <div className="max-w-2xl mx-auto">
        <div className="text-center mb-8">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-3">
            Purpose-Built for Agent Failure Detection
          </h2>
          <p className="text-zinc-400 text-lg">
            General observability tools track LLM calls. PISAMA detects when multi-agent systems fail.
          </p>
        </div>

        {/* Desktop Table */}
        <div className="hidden lg:block overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b border-zinc-700">
                <th className="text-left py-3 px-3 text-zinc-400 font-medium">Capability</th>
                <th className="text-center py-3 px-3">
                  <div className="text-white font-semibold">PISAMA</div>
                </th>
                <th className="text-center py-3 px-3 text-zinc-400 font-medium">General observability</th>
              </tr>
            </thead>
            <tbody>
              {features.map((category, catIndex) => (
                <Fragment key={`cat-${catIndex}`}>
                  <tr>
                    <td colSpan={3} className="pt-3 pb-1 px-3">
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
                      <td className="py-2 px-3 text-zinc-300">{row.name}</td>
                      <td className="py-2 px-3 bg-blue-500/5">{renderCell(row.pisama)}</td>
                      <td className="py-2 px-3">{renderCell(row.others)}</td>
                    </tr>
                  ))}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>

        {/* Mobile Cards */}
        <div className="lg:hidden space-y-4">
          {features.map((category, catIndex) => (
            <div key={catIndex} className="bg-zinc-800/50 rounded-xl p-4 border border-zinc-700">
              <h3 className="text-white font-semibold mb-3">{category.category}</h3>
              <div className="space-y-2">
                {category.rows.map((row, rowIndex) => (
                  <div key={rowIndex} className="flex justify-between items-center">
                    <span className="text-zinc-300 text-sm">{row.name}</span>
                    {renderCell(row.pisama)}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Legend */}
        <div className="mt-6 flex flex-wrap gap-6 justify-center text-sm text-zinc-400">
          <div className="flex items-center gap-2">
            <Check className="w-4 h-4 text-green-400" />
            <span>Supported</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-amber-400">Varies</span>
            <span>Depends on tool</span>
          </div>
          <div className="flex items-center gap-2">
            <X className="w-4 h-4 text-zinc-600" />
            <span>Not available</span>
          </div>
        </div>
      </div>
    </section>
  )
}
