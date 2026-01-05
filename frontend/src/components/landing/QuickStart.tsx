'use client'

import { Terminal } from 'lucide-react'

const commands = [
  { cmd: 'pisama-cc install', desc: 'Install capture hooks' },
  { cmd: 'pisama-cc traces', desc: 'View recent traces' },
  { cmd: 'pisama-cc usage --by-model', desc: 'Token breakdown by model' },
  { cmd: 'pisama-cc export -o traces.jsonl', desc: 'Export to JSONL' },
]

export function QuickStart() {
  return (
    <section className="py-20 px-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center gap-3 mb-8">
          <Terminal className="w-6 h-6 text-primary-400" />
          <h2 className="text-2xl md:text-3xl font-bold text-white">
            Quick Start
          </h2>
        </div>

        <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
          {/* Terminal Header */}
          <div className="bg-slate-900 px-4 py-3 flex items-center gap-2 border-b border-slate-700">
            <div className="w-3 h-3 rounded-full bg-red-500" />
            <div className="w-3 h-3 rounded-full bg-yellow-500" />
            <div className="w-3 h-3 rounded-full bg-green-500" />
            <span className="text-slate-500 text-sm ml-2 font-mono">terminal</span>
          </div>

          {/* Commands */}
          <div className="p-6 font-mono text-sm space-y-4">
            {commands.map((item, i) => (
              <div key={i} className="group">
                <div className="flex items-start gap-3">
                  <span className="text-emerald-400 select-none">$</span>
                  <span className="text-white">{item.cmd}</span>
                </div>
                <div className="text-slate-500 ml-5 mt-1 text-xs">
                  # {item.desc}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Example Output */}
        <div className="mt-8 bg-slate-800/50 border border-slate-700 rounded-xl p-6">
          <h3 className="text-sm font-medium text-slate-400 mb-4">Example: pisama-cc status</h3>
          <pre className="font-mono text-xs text-slate-300 overflow-x-auto">
{`PISAMA Status
========================================

Hook Installation:
   pisama-capture.py
   pisama-pre.sh
   pisama-post.sh
   All hooks installed

Local Traces: 1,400
   Input tokens:  9,580
   Output tokens: 79,569
   Total cost:    $43.22
   Models: claude-opus-4-5-20251101`}
          </pre>
        </div>
      </div>
    </section>
  )
}
