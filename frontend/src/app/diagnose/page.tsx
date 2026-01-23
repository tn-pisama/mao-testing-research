'use client'

export const dynamic = 'force-dynamic'

import { useState, useCallback } from 'react'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import { Layout } from '@/components/common/Layout'
import { TracePasteInput } from '@/components/diagnose/TracePasteInput'
import { DiagnosisResults } from '@/components/diagnose/DiagnosisResults'
import { createApiClient, DiagnoseResult } from '@/lib/api'
import { AlertCircle, Loader2, Search } from 'lucide-react'

export default function DiagnosePage() {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const [traceContent, setTraceContent] = useState('')
  const [format, setFormat] = useState('auto')
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [result, setResult] = useState<DiagnoseResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleAnalyze = useCallback(async () => {
    if (!traceContent.trim()) {
      setError('Please paste a trace to analyze')
      return
    }

    setIsAnalyzing(true)
    setError(null)
    setResult(null)

    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      const diagnosis = await api.diagnoseTrace(traceContent, format)
      setResult(diagnosis)
    } catch (err) {
      console.error('Failed to analyze trace:', err)
      setError('Failed to analyze trace. Please check your connection and try again.')
    } finally {
      setIsAnalyzing(false)
    }
  }, [traceContent, format, getToken, tenantId])

  const handleClear = useCallback(() => {
    setTraceContent('')
    setResult(null)
    setError(null)
  }, [])

  return (
    <Layout>
      <div className="p-6 max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-primary-600/20 rounded-lg">
              <Search className="w-6 h-6 text-primary-400" />
            </div>
            <h1 className="text-2xl font-bold text-white">Agent Forensics</h1>
            <span className="px-2 py-0.5 text-xs font-medium bg-purple-500/20 text-purple-400 rounded-full">
              Beta
            </span>
          </div>
          <p className="text-slate-400">
            Paste your trace and find out why your AI agent failed - and how to fix it.
          </p>
        </div>

        {/* Main Content */}
        <div className="grid lg:grid-cols-2 gap-6">
          {/* Left: Input */}
          <div className="space-y-4">
            <TracePasteInput
              value={traceContent}
              onChange={setTraceContent}
              format={format}
              onFormatChange={setFormat}
              disabled={isAnalyzing}
            />

            {/* Error */}
            {error && (
              <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg flex items-center gap-3">
                <AlertCircle className="w-5 h-5 text-red-400" />
                <p className="text-red-300 text-sm">{error}</p>
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-3">
              <button
                onClick={handleAnalyze}
                disabled={isAnalyzing || !traceContent.trim()}
                className="flex-1 py-3 px-4 bg-primary-600 hover:bg-primary-500 disabled:bg-slate-700 disabled:text-slate-500 text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
              >
                {isAnalyzing ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    <Search className="w-5 h-5" />
                    Diagnose
                  </>
                )}
              </button>
              {(traceContent || result) && (
                <button
                  onClick={handleClear}
                  disabled={isAnalyzing}
                  className="py-3 px-4 bg-slate-700 hover:bg-slate-600 text-slate-300 font-medium rounded-lg transition-colors"
                >
                  Clear
                </button>
              )}
            </div>
          </div>

          {/* Right: Results */}
          <div>
            {result ? (
              <DiagnosisResults result={result} />
            ) : (
              <div className="h-full flex items-center justify-center bg-slate-800/50 rounded-xl border border-slate-700 border-dashed p-8">
                <div className="text-center text-slate-500">
                  <Search className="w-12 h-12 mx-auto mb-4 opacity-50" />
                  <p className="text-lg font-medium mb-2">No diagnosis yet</p>
                  <p className="text-sm">Paste a trace and click Diagnose to see results</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Supported Formats */}
        <div className="mt-8 p-6 bg-slate-800/50 rounded-xl border border-slate-700">
          <h3 className="text-lg font-semibold text-white mb-4">Supported Formats</h3>
          <div className="grid md:grid-cols-4 gap-4">
            {[
              { name: 'Auto', desc: 'Auto-detect format from content' },
              { name: 'LangSmith', desc: 'LangChain trace exports (JSONL/JSON)' },
              { name: 'OpenTelemetry', desc: 'OTEL spans (resourceSpans format)' },
              { name: 'Raw JSON', desc: 'Any JSON with agent/tool info' },
            ].map((fmt) => (
              <div key={fmt.name} className="p-4 bg-slate-900/50 rounded-lg">
                <h4 className="font-medium text-white mb-1">{fmt.name}</h4>
                <p className="text-sm text-slate-400">{fmt.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Layout>
  )
}
