'use client'

import { useState } from 'react'
import { GitBranch, Users, Zap, Workflow, Blocks, Bot, Copy, Check, ArrowRight } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { FRAMEWORKS } from '@/hooks/useOnboarding'

import type { LucideIcon } from 'lucide-react'

const ICON_MAP: Record<string, LucideIcon> = {
  GitBranch, Users, Zap, Workflow, Blocks, Bot,
}

interface StepConnectProps {
  selectedFramework: string | null
  onSelectFramework: (framework: string) => void
  onNext: () => void
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <button
      onClick={handleCopy}
      className="p-2 hover:bg-zinc-700 rounded transition-colors"
      title="Copy to clipboard"
    >
      {copied ? (
        <Check className="w-4 h-4 text-green-400" />
      ) : (
        <Copy className="w-4 h-4 text-zinc-400" />
      )}
    </button>
  )
}

export function StepConnect({ selectedFramework, onSelectFramework, onNext }: StepConnectProps) {
  const selected = FRAMEWORKS.find(f => f.id === selectedFramework)

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-2xl font-bold text-zinc-100">Choose Your Agent Framework</h2>
        <p className="text-zinc-400 mt-2">
          Select the framework you&apos;re using to get setup instructions
        </p>
      </div>

      {/* Framework cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {FRAMEWORKS.map((fw) => {
          const Icon = ICON_MAP[fw.icon] || Zap
          const isSelected = selectedFramework === fw.id
          return (
            <Card
              key={fw.id}
              className={`cursor-pointer transition-all ${
                isSelected
                  ? 'border-blue-500 bg-blue-500/10'
                  : 'border-zinc-800 hover:border-zinc-600 bg-zinc-900'
              }`}
              onClick={() => onSelectFramework(fw.id)}
            >
              <CardContent className="p-4 flex flex-col items-center text-center gap-2">
                <Icon className={`w-8 h-8 ${isSelected ? 'text-blue-400' : 'text-zinc-400'}`} />
                <span className={`font-medium ${isSelected ? 'text-blue-300' : 'text-zinc-200'}`}>
                  {fw.name}
                </span>
                <span className="text-xs text-zinc-500">{fw.description}</span>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* Setup instructions */}
      {selected && (
        <div className="space-y-4 mt-6">
          <h3 className="text-lg font-semibold text-zinc-200">
            Setup Instructions for {selected.name}
          </h3>

          {selected.pipInstall && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-zinc-500 uppercase tracking-wider">Install</span>
                <CopyButton text={selected.pipInstall} />
              </div>
              <code className="text-sm text-green-400 font-mono">{selected.pipInstall}</code>
            </div>
          )}

          <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-zinc-500 uppercase tracking-wider">
                {selected.isVisual ? 'Configuration' : 'Code'}
              </span>
              <CopyButton text={selected.codeSnippet} />
            </div>
            <pre className="text-sm text-zinc-300 font-mono whitespace-pre-wrap overflow-x-auto">
              {selected.codeSnippet}
            </pre>
          </div>

          <Button onClick={onNext} className="w-full">
            I&apos;ve Set Up the Integration
            <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
        </div>
      )}
    </div>
  )
}
