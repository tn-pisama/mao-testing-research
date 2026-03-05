'use client'

import { useMemo } from 'react'
import { FileCode } from 'lucide-react'

interface DiffLine {
  type: 'context' | 'addition' | 'deletion' | 'header'
  content: string
  oldLineNum?: number
  newLineNum?: number
}

function parseDiff(diff: string): DiffLine[] {
  const lines = diff.split('\n')
  const result: DiffLine[] = []
  let oldLine = 0
  let newLine = 0

  for (const line of lines) {
    if (line.startsWith('@@')) {
      // Parse hunk header like @@ -1,5 +1,7 @@
      const match = line.match(/@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/)
      if (match) {
        oldLine = parseInt(match[1], 10)
        newLine = parseInt(match[2], 10)
      }
      result.push({ type: 'header', content: line })
    } else if (line.startsWith('---') || line.startsWith('+++')) {
      // File headers, skip or treat as header
      result.push({ type: 'header', content: line })
    } else if (line.startsWith('-')) {
      result.push({ type: 'deletion', content: line.slice(1), oldLineNum: oldLine })
      oldLine++
    } else if (line.startsWith('+')) {
      result.push({ type: 'addition', content: line.slice(1), newLineNum: newLine })
      newLine++
    } else {
      // Context line (may start with a space)
      const content = line.startsWith(' ') ? line.slice(1) : line
      if (content || line === '') {
        result.push({ type: 'context', content, oldLineNum: oldLine, newLineNum: newLine })
        oldLine++
        newLine++
      }
    }
  }

  return result
}

interface CodeDiffViewerProps {
  diff: string
  filePath?: string
  className?: string
}

export function CodeDiffViewer({ diff, filePath, className = '' }: CodeDiffViewerProps) {
  const parsedLines = useMemo(() => parseDiff(diff), [diff])

  if (!diff.trim()) {
    return (
      <div className={`bg-zinc-950 border border-zinc-800 rounded-lg p-6 text-center ${className}`}>
        <p className="text-zinc-500 text-sm">No diff available</p>
      </div>
    )
  }

  return (
    <div className={`bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden ${className}`}>
      {/* File path header */}
      {filePath && (
        <div className="flex items-center gap-2 px-4 py-2 bg-zinc-900 border-b border-zinc-800">
          <FileCode size={14} className="text-zinc-500" />
          <span className="text-sm font-mono text-zinc-300">{filePath}</span>
        </div>
      )}

      {/* Diff content */}
      <div className="overflow-x-auto">
        <pre className="text-sm leading-relaxed">
          {parsedLines.map((line, i) => {
            let bgClass = ''
            let textClass = 'text-zinc-400'
            let prefix = ' '

            switch (line.type) {
              case 'addition':
                bgClass = 'bg-green-500/10'
                textClass = 'text-green-300'
                prefix = '+'
                break
              case 'deletion':
                bgClass = 'bg-red-500/10'
                textClass = 'text-red-300'
                prefix = '-'
                break
              case 'header':
                bgClass = 'bg-blue-500/5'
                textClass = 'text-blue-400'
                prefix = ''
                break
              case 'context':
              default:
                textClass = 'text-zinc-400'
                prefix = ' '
                break
            }

            return (
              <div
                key={i}
                className={`flex ${bgClass} hover:brightness-110 transition-[filter]`}
              >
                {/* Line numbers */}
                {line.type !== 'header' && (
                  <>
                    <span className="w-12 text-right pr-2 text-zinc-600 select-none flex-shrink-0 text-xs leading-relaxed">
                      {line.type !== 'addition' && line.oldLineNum !== undefined ? line.oldLineNum : ''}
                    </span>
                    <span className="w-12 text-right pr-2 text-zinc-600 select-none flex-shrink-0 text-xs leading-relaxed border-r border-zinc-800 mr-2">
                      {line.type !== 'deletion' && line.newLineNum !== undefined ? line.newLineNum : ''}
                    </span>
                  </>
                )}
                {line.type === 'header' && (
                  <span className="w-[6.5rem] flex-shrink-0 border-r border-zinc-800 mr-2" />
                )}
                <span className={`${textClass} font-mono whitespace-pre px-2 flex-1`}>
                  {line.type === 'header' ? line.content : `${prefix}${line.content}`}
                </span>
              </div>
            )
          })}
        </pre>
      </div>
    </div>
  )
}
