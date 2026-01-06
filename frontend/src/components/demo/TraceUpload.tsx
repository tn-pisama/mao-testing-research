'use client'

import { useState, useCallback } from 'react'
import {
  Upload, FileJson, AlertTriangle, CheckCircle, X,
  Loader2, FileText, AlertCircle
} from 'lucide-react'
import { Button } from '@/components/ui/Button'

interface Detection {
  type: string
  confidence: number
  method: string
  explanation: string
  loopStart?: number
  loopLength?: number
}

interface UploadResult {
  success: boolean
  traceId?: string
  stateCount?: number
  detections?: Detection[]
  error?: string
}

interface TraceUploadProps {
  onDetectionFound?: (detections: Detection[]) => void
}

export function TraceUpload({ onDetectionFound }: TraceUploadProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)
  const [result, setResult] = useState<UploadResult | null>(null)
  const [fileName, setFileName] = useState<string | null>(null)

  const processTrace = useCallback(async (file: File) => {
    setIsProcessing(true)
    setFileName(file.name)
    setResult(null)

    try {
      const content = await file.text()
      let traces: any[] = []

      // Parse JSONL or JSON
      if (file.name.endsWith('.jsonl')) {
        traces = content
          .split('\n')
          .filter(line => line.trim())
          .map(line => JSON.parse(line))
      } else {
        const parsed = JSON.parse(content)
        traces = Array.isArray(parsed) ? parsed : [parsed]
      }

      if (traces.length === 0) {
        setResult({ success: false, error: 'No traces found in file' })
        return
      }

      // Analyze first trace for demo purposes
      const trace = traces[0]
      const states = trace.states || trace.trace || trace.spans || []

      // Simple client-side detection simulation
      // In production this would call the backend API
      const detections: Detection[] = []

      // Check for loops (simplified)
      if (states.length >= 3) {
        const lastThreeContents = states.slice(-3).map((s: any) =>
          JSON.stringify(s.content || s.state || s)
        )

        if (lastThreeContents[0] === lastThreeContents[1] &&
            lastThreeContents[1] === lastThreeContents[2]) {
          detections.push({
            type: 'infinite_loop',
            confidence: 0.92,
            method: 'structural',
            explanation: 'Detected exact repetition in the last 3 states. The agent appears to be stuck in a loop.',
            loopStart: states.length - 3,
            loopLength: 3,
          })
        }
      }

      // Check for failure mode markers
      const failureMode = trace.failure_mode || trace.failureMode
      if (failureMode && failureMode !== 'healthy') {
        const modeDescriptions: Record<string, string> = {
          'F1': 'Exact message loop detected',
          'F3': 'Semantic loop - same meaning, different wording',
          'F6': 'Task derailment - agent went off-topic',
          'F11': 'Coordination failure between agents',
        }

        detections.push({
          type: failureMode,
          confidence: 0.95,
          method: 'marker',
          explanation: modeDescriptions[failureMode] || `Failure mode ${failureMode} detected in trace`,
        })
      }

      setResult({
        success: true,
        traceId: trace.trace_id || trace.id || 'unknown',
        stateCount: states.length,
        detections,
      })

      if (detections.length > 0 && onDetectionFound) {
        onDetectionFound(detections)
      }
    } catch (err) {
      setResult({
        success: false,
        error: err instanceof Error ? err.message : 'Failed to parse trace file',
      })
    } finally {
      setIsProcessing(false)
    }
  }, [onDetectionFound])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)

    const file = e.dataTransfer.files[0]
    if (file && (file.name.endsWith('.json') || file.name.endsWith('.jsonl'))) {
      processTrace(file)
    }
  }, [processTrace])

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      processTrace(file)
    }
  }, [processTrace])

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const handleClear = () => {
    setResult(null)
    setFileName(null)
  }

  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-700 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Upload size={16} className="text-indigo-400" />
          <h3 className="text-sm font-medium text-white">Try Your Own Trace</h3>
        </div>
        {result && (
          <button
            onClick={handleClear}
            className="p-1 text-slate-400 hover:text-white transition-colors"
          >
            <X size={14} />
          </button>
        )}
      </div>

      <div className="p-4">
        {!result && !isProcessing && (
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors ${
              isDragging
                ? 'border-indigo-500 bg-indigo-500/10'
                : 'border-slate-600 hover:border-slate-500'
            }`}
          >
            <FileJson size={32} className="mx-auto text-slate-400 mb-3" />
            <p className="text-sm text-slate-300 mb-2">
              Drop a trace file here
            </p>
            <p className="text-xs text-slate-500 mb-4">
              Supports .json and .jsonl formats
            </p>
            <label className="cursor-pointer">
              <input
                type="file"
                accept=".json,.jsonl"
                onChange={handleFileSelect}
                className="hidden"
              />
              <span className="inline-flex items-center justify-center px-4 py-2 text-sm font-medium rounded-lg bg-slate-700 text-white hover:bg-slate-600 transition-colors">
                Browse Files
              </span>
            </label>
          </div>
        )}

        {isProcessing && (
          <div className="py-8 text-center">
            <Loader2 size={32} className="mx-auto text-indigo-400 animate-spin mb-3" />
            <p className="text-sm text-slate-300">Analyzing {fileName}...</p>
          </div>
        )}

        {result && (
          <div className="space-y-4">
            {result.success ? (
              <>
                <div className="flex items-center gap-2 text-emerald-400">
                  <CheckCircle size={16} />
                  <span className="text-sm font-medium">Trace Analyzed</span>
                </div>

                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div className="bg-slate-900/50 rounded-lg p-3">
                    <span className="text-slate-400 text-xs">Trace ID</span>
                    <p className="text-white font-mono text-xs truncate mt-1">
                      {result.traceId}
                    </p>
                  </div>
                  <div className="bg-slate-900/50 rounded-lg p-3">
                    <span className="text-slate-400 text-xs">States</span>
                    <p className="text-white font-semibold mt-1">
                      {result.stateCount}
                    </p>
                  </div>
                </div>

                {result.detections && result.detections.length > 0 ? (
                  <div className="space-y-2">
                    <h4 className="text-xs font-medium text-slate-400">
                      Detections ({result.detections.length})
                    </h4>
                    {result.detections.map((detection, i) => (
                      <div
                        key={i}
                        className="bg-red-500/10 border border-red-500/30 rounded-lg p-3"
                      >
                        <div className="flex items-center gap-2 mb-2">
                          <AlertTriangle size={14} className="text-red-400" />
                          <span className="text-sm font-medium text-white">
                            {detection.type}
                          </span>
                          <span className="text-xs text-slate-400">
                            {Math.round(detection.confidence * 100)}% confidence
                          </span>
                        </div>
                        <p className="text-xs text-slate-300">
                          {detection.explanation}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-3">
                    <div className="flex items-center gap-2">
                      <CheckCircle size={14} className="text-emerald-400" />
                      <span className="text-sm text-emerald-300">
                        No failures detected
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-1">
                      This trace appears healthy
                    </p>
                  </div>
                )}
              </>
            ) : (
              <div className="flex items-start gap-2 text-red-400">
                <AlertCircle size={16} className="mt-0.5" />
                <div>
                  <span className="text-sm font-medium">Analysis Failed</span>
                  <p className="text-xs text-slate-400 mt-1">{result.error}</p>
                </div>
              </div>
            )}

            <Button
              variant="secondary"
              size="sm"
              onClick={handleClear}
              className="w-full"
            >
              Upload Another File
            </Button>
          </div>
        )}
      </div>

      <div className="px-4 py-3 border-t border-slate-700 bg-slate-900/30">
        <p className="text-xs text-slate-500">
          For full analysis, import traces via the{' '}
          <a href="/import" className="text-indigo-400 hover:underline">
            Import page
          </a>
        </p>
      </div>
    </div>
  )
}
