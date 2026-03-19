'use client'

import { useState } from 'react'
import { ChevronDown, ChevronUp, Copy, Check } from 'lucide-react'

interface CodeDiffViewerProps {
  diff: string
  language?: string
  collapsed?: boolean
}

export function CodeDiffViewer({ diff, language = 'python', collapsed = false }: CodeDiffViewerProps) {
  const [isCollapsed, setIsCollapsed] = useState(collapsed)
  const [copied, setCopied] = useState(false)

  const lines = diff.split('\n')

  const handleCopy = async () => {
    await navigator.clipboard.writeText(diff)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="border border-zinc-700 rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 bg-zinc-800/80 border-b border-zinc-700">
        <span className="text-xs text-zinc-400 font-mono">{language}</span>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            className="text-zinc-400 hover:text-white transition-colors p-1"
            title="Copy to clipboard"
          >
            {copied ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
          </button>
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="text-zinc-400 hover:text-white transition-colors p-1"
          >
            {isCollapsed ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
          </button>
        </div>
      </div>
      {!isCollapsed && (
        <div className="overflow-x-auto">
          <pre className="text-xs leading-relaxed">
            {lines.map((line, idx) => {
              let bgColor = ''
              let textColor = 'text-zinc-300'

              if (line.startsWith('+++ ') || line.startsWith('--- ')) {
                bgColor = 'bg-zinc-800/50'
                textColor = 'text-zinc-400'
              } else if (line.startsWith('@@')) {
                bgColor = 'bg-blue-500/10'
                textColor = 'text-blue-400'
              } else if (line.startsWith('+')) {
                bgColor = 'bg-green-500/10'
                textColor = 'text-green-300'
              } else if (line.startsWith('-')) {
                bgColor = 'bg-red-500/10'
                textColor = 'text-red-300'
              }

              return (
                <div
                  key={idx}
                  className={`px-3 py-0.5 ${bgColor} ${textColor} font-mono whitespace-pre`}
                >
                  <span className="inline-block w-8 text-right mr-3 text-zinc-600 select-none">
                    {idx + 1}
                  </span>
                  {line}
                </div>
              )
            })}
          </pre>
        </div>
      )}
    </div>
  )
}
