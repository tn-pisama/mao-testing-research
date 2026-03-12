'use client'

import { useState } from 'react'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import {
  FileCode,
  AlertTriangle,
  Copy,
  Check,
  Download,
  Shield,
  Sparkles,
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { createApiClient, SourceFix } from '@/lib/api'
import { CodeDiffViewer } from './CodeDiffViewer'

const LANGUAGES = [
  { value: 'python', label: 'Python' },
  { value: 'typescript', label: 'TypeScript' },
  { value: 'javascript', label: 'JavaScript' },
  { value: 'go', label: 'Go' },
  { value: 'rust', label: 'Rust' },
]

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100)
  let variant: 'success' | 'warning' | 'error' = 'success'
  if (pct < 70) variant = 'error'
  else if (pct < 85) variant = 'warning'
  return (
    <Badge variant={variant} size="sm">
      {pct}% confidence
    </Badge>
  )
}

function RiskBadge({ risk }: { risk: string }) {
  const config: Record<string, { variant: 'success' | 'warning' | 'error'; label: string }> = {
    low: { variant: 'success', label: 'Low Risk' },
    medium: { variant: 'warning', label: 'Medium Risk' },
    high: { variant: 'error', label: 'High Risk' },
  }
  const c = config[risk.toLowerCase()] ?? config.medium
  return (
    <Badge variant={c.variant} size="sm">
      <Shield size={10} className="mr-1" />
      {c.label}
    </Badge>
  )
}

interface SourceFixPanelProps {
  detectionId: string
  className?: string
}

export function SourceFixPanel({ detectionId, className = '' }: SourceFixPanelProps) {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()

  // Input state
  const [fileContent, setFileContent] = useState('')
  const [filePath, setFilePath] = useState('')
  const [language, setLanguage] = useState('python')
  const [framework, setFramework] = useState('')

  // Output state
  const [fix, setFix] = useState<SourceFix | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const handleGenerate = async () => {
    if (!fileContent.trim() || !filePath.trim()) return
    setIsGenerating(true)
    setError(null)
    setFix(null)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      const result = await api.generateSourceFix(detectionId, {
        file_path: filePath.trim(),
        file_content: fileContent,
        language,
        framework: framework.trim() || undefined,
      })
      setFix(result)
    } catch (err) {
      console.warn('Failed to generate source fix:', err)
      setError((err as Error).message || 'Failed to generate fix. Please try again.')
    }
    setIsGenerating(false)
  }

  const handleCopyPatch = async () => {
    if (!fix) return
    await navigator.clipboard.writeText(fix.unified_diff)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleDownloadPatch = () => {
    if (!fix) return
    const blob = new Blob([fix.unified_diff], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `fix-${fix.id.slice(0, 8)}.patch`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  return (
    <div className={className}>
      <Card padding="lg">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Sparkles size={18} className="text-violet-400" />
            <CardTitle className="text-base">Generate Source Fix</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          {/* File path input */}
          <div className="mb-3">
            <label className="block text-sm text-zinc-400 mb-1">File Path</label>
            <input
              type="text"
              value={filePath}
              onChange={(e) => setFilePath(e.target.value)}
              placeholder="e.g. src/agents/coordinator.py"
              className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30"
            />
          </div>

          {/* Language and framework selectors */}
          <div className="flex gap-3 mb-3">
            <div className="flex-1">
              <label className="block text-sm text-zinc-400 mb-1">Language</label>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30"
              >
                {LANGUAGES.map((lang) => (
                  <option key={lang.value} value={lang.value}>
                    {lang.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex-1">
              <label className="block text-sm text-zinc-400 mb-1">Framework (optional)</label>
              <input
                type="text"
                value={framework}
                onChange={(e) => setFramework(e.target.value)}
                placeholder="e.g. langgraph, crewai"
                className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30"
              />
            </div>
          </div>

          {/* File content textarea */}
          <div className="mb-4">
            <label className="block text-sm text-zinc-400 mb-1">File Content</label>
            <textarea
              value={fileContent}
              onChange={(e) => setFileContent(e.target.value)}
              placeholder="Paste the source file content here..."
              className="w-full h-48 bg-zinc-950 border border-zinc-700 rounded-lg p-3 text-sm text-zinc-200 font-mono placeholder-zinc-500 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30 resize-y"
            />
          </div>

          {/* Error */}
          {error && (
            <div className="mb-4 flex items-center gap-2 text-sm text-red-400">
              <AlertTriangle size={14} />
              <span>{error}</span>
            </div>
          )}

          {/* Generate button */}
          <Button
            onClick={handleGenerate}
            disabled={!fileContent.trim() || !filePath.trim() || isGenerating}
            isLoading={isGenerating}
            leftIcon={<FileCode size={16} />}
          >
            Generate Source Fix
          </Button>
        </CardContent>
      </Card>

      {/* Fix Result */}
      {fix && (
        <Card className="mt-4" padding="lg">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileCode size={18} className="text-green-400" />
                <CardTitle className="text-base">Generated Fix</CardTitle>
              </div>
              <div className="flex items-center gap-2">
                <ConfidenceBadge confidence={fix.confidence} />
                <RiskBadge risk={fix.breaking_risk} />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {/* Explanation */}
            <div className="mb-4">
              <h4 className="text-sm font-medium text-zinc-300 mb-1">Explanation</h4>
              <p className="text-sm text-zinc-400">{fix.explanation}</p>
            </div>

            {/* Root cause */}
            {fix.root_cause && (
              <div className="mb-4">
                <h4 className="text-sm font-medium text-zinc-300 mb-1">Root Cause</h4>
                <p className="text-sm text-zinc-400">{fix.root_cause}</p>
              </div>
            )}

            {/* Diff viewer */}
            <div className="mb-4">
              <h4 className="text-sm font-medium text-zinc-300 mb-2">Code Changes</h4>
              <CodeDiffViewer diff={fix.unified_diff} filePath={fix.file_path} />
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={handleCopyPatch}
                leftIcon={copied ? <Check size={14} /> : <Copy size={14} />}
              >
                {copied ? 'Copied' : 'Copy Patch'}
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={handleDownloadPatch}
                leftIcon={<Download size={14} />}
              >
                Download .patch
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
