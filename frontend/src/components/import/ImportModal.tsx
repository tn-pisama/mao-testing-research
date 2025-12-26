'use client'

import { useState, useCallback } from 'react'
import { X, Upload, FileJson, AlertCircle, CheckCircle2, Loader2 } from 'lucide-react'
import { Button } from '../ui/Button'

interface ImportModalProps {
  isOpen: boolean
  onClose: () => void
  onImportComplete?: (jobId: string) => void
}

type ImportStatus = 'idle' | 'uploading' | 'processing' | 'completed' | 'error'

interface ImportJob {
  id: string
  status: string
  format: string
  file_name: string
  records_total: number
  records_processed: number
  records_failed: number
  traces_created: number
  detections_found: number
  error_message?: string
}

export function ImportModal({ isOpen, onClose, onImportComplete }: ImportModalProps) {
  const [file, setFile] = useState<File | null>(null)
  const [format, setFormat] = useState('auto')
  const [status, setStatus] = useState<ImportStatus>('idle')
  const [importJob, setImportJob] = useState<ImportJob | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const droppedFile = e.dataTransfer.files[0]
    if (droppedFile && (droppedFile.name.endsWith('.json') || droppedFile.name.endsWith('.jsonl'))) {
      setFile(droppedFile)
      setError(null)
    } else {
      setError('Please upload a .json or .jsonl file')
    }
  }, [])

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (selectedFile) {
      setFile(selectedFile)
      setError(null)
    }
  }

  const startImport = async () => {
    if (!file) return

    setStatus('uploading')
    setError(null)

    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('format', format)

      const response = await fetch('/api/v1/import-jobs', {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'Import failed')
      }

      const job = await response.json()
      setImportJob(job)
      setStatus('processing')

      pollJobStatus(job.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed')
      setStatus('error')
    }
  }

  const pollJobStatus = async (jobId: string) => {
    const poll = async () => {
      try {
        const response = await fetch(`/api/v1/import-jobs/${jobId}`)
        const job = await response.json()
        setImportJob(job)

        if (job.status === 'completed') {
          setStatus('completed')
          onImportComplete?.(jobId)
        } else if (job.status === 'failed') {
          setError(job.error_message || 'Import failed')
          setStatus('error')
        } else {
          setTimeout(poll, 1000)
        }
      } catch {
        setTimeout(poll, 2000)
      }
    }

    poll()
  }

  const reset = () => {
    setFile(null)
    setFormat('auto')
    setStatus('idle')
    setImportJob(null)
    setError(null)
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      
      <div className="relative bg-slate-800 rounded-xl shadow-2xl w-full max-w-lg mx-4 border border-slate-700">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700">
          <h2 className="text-lg font-semibold text-white">Import Historical Data</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
            <X size={20} />
          </button>
        </div>

        <div className="p-6">
          {status === 'idle' && (
            <>
              <div
                onDrop={handleDrop}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
                onDragLeave={() => setDragOver(false)}
                className={`
                  border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer
                  ${dragOver ? 'border-primary-500 bg-primary-500/10' : 'border-slate-600 hover:border-slate-500'}
                `}
                onClick={() => document.getElementById('file-input')?.click()}
              >
                <input
                  id="file-input"
                  type="file"
                  accept=".json,.jsonl"
                  onChange={handleFileSelect}
                  className="hidden"
                />
                
                {file ? (
                  <div className="flex items-center justify-center gap-3">
                    <FileJson className="text-primary-400" size={24} />
                    <div className="text-left">
                      <p className="text-white font-medium">{file.name}</p>
                      <p className="text-slate-400 text-sm">
                        {(file.size / 1024 / 1024).toFixed(2)} MB
                      </p>
                    </div>
                  </div>
                ) : (
                  <>
                    <Upload className="mx-auto text-slate-400 mb-3" size={32} />
                    <p className="text-white mb-1">Drag & drop your file here</p>
                    <p className="text-slate-400 text-sm">or click to browse</p>
                    <p className="text-slate-500 text-xs mt-2">
                      Supports: LangSmith, Langfuse, OTLP JSON
                    </p>
                  </>
                )}
              </div>

              <div className="mt-4">
                <label className="block text-sm text-slate-400 mb-2">Format</label>
                <select
                  value={format}
                  onChange={(e) => setFormat(e.target.value)}
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  <option value="auto">Auto-detect</option>
                  <option value="langsmith">LangSmith</option>
                  <option value="langfuse">Langfuse</option>
                  <option value="otlp">OTLP JSON</option>
                  <option value="generic">Generic JSONL</option>
                </select>
              </div>

              {error && (
                <div className="mt-4 flex items-center gap-2 text-red-400 bg-red-400/10 rounded-lg px-4 py-3">
                  <AlertCircle size={18} />
                  <span className="text-sm">{error}</span>
                </div>
              )}
            </>
          )}

          {(status === 'uploading' || status === 'processing') && importJob && (
            <div className="text-center py-4">
              <Loader2 className="animate-spin mx-auto text-primary-400 mb-4" size={40} />
              <p className="text-white font-medium mb-2">
                {status === 'uploading' ? 'Uploading...' : 'Processing...'}
              </p>
              
              <div className="bg-slate-700 rounded-full h-2 mb-4 overflow-hidden">
                <div
                  className="bg-primary-500 h-full transition-all duration-300"
                  style={{
                    width: `${Math.round((importJob.records_processed / Math.max(importJob.records_total, 1)) * 100)}%`
                  }}
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div className="bg-slate-700/50 rounded-lg p-3">
                  <p className="text-slate-400">Processed</p>
                  <p className="text-white font-medium">
                    {importJob.records_processed} / {importJob.records_total}
                  </p>
                </div>
                <div className="bg-slate-700/50 rounded-lg p-3">
                  <p className="text-slate-400">Detections</p>
                  <p className="text-white font-medium">{importJob.detections_found}</p>
                </div>
              </div>
            </div>
          )}

          {status === 'completed' && importJob && (
            <div className="text-center py-4">
              <CheckCircle2 className="mx-auto text-emerald-400 mb-4" size={48} />
              <p className="text-white font-medium text-lg mb-4">Import Complete!</p>
              
              <div className="grid grid-cols-2 gap-3 mb-4">
                <div className="bg-slate-700/50 rounded-lg p-3">
                  <p className="text-slate-400 text-sm">Traces Imported</p>
                  <p className="text-white font-semibold text-xl">{importJob.traces_created}</p>
                </div>
                <div className="bg-slate-700/50 rounded-lg p-3">
                  <p className="text-slate-400 text-sm">Records</p>
                  <p className="text-white font-semibold text-xl">{importJob.records_processed}</p>
                </div>
              </div>
              
              {importJob.detections_found > 0 && (
                <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4 mb-4">
                  <p className="text-amber-400 font-medium">
                    {importJob.detections_found} issues detected
                  </p>
                  <p className="text-amber-400/70 text-sm mt-1">
                    View detections to see details and fix suggestions
                  </p>
                </div>
              )}
              
              {importJob.records_failed > 0 && (
                <p className="text-slate-400 text-sm">
                  {importJob.records_failed} records failed to import
                </p>
              )}
            </div>
          )}

          {status === 'error' && (
            <div className="text-center py-4">
              <AlertCircle className="mx-auto text-red-400 mb-4" size={48} />
              <p className="text-white font-medium mb-2">Import Failed</p>
              <p className="text-red-400 text-sm">{error}</p>
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-700">
          {status === 'idle' && (
            <>
              <Button variant="ghost" onClick={onClose}>Cancel</Button>
              <Button onClick={startImport} disabled={!file}>Start Import</Button>
            </>
          )}
          
          {status === 'completed' && (
            <>
              <Button variant="ghost" onClick={reset}>Import Another</Button>
              <Button onClick={onClose}>View Detections</Button>
            </>
          )}
          
          {status === 'error' && (
            <>
              <Button variant="ghost" onClick={onClose}>Cancel</Button>
              <Button onClick={reset}>Try Again</Button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
