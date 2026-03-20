'use client'

import { useState } from 'react'
import { X, Upload, FileJson, CheckCircle, AlertCircle } from 'lucide-react'
import { Button } from '../ui/Button'

interface ImportModalProps {
  isOpen: boolean
  onClose: () => void
  onImportComplete?: () => void
}

export function ImportModal({ isOpen, onClose, onImportComplete }: ImportModalProps) {
  const [file, setFile] = useState<File | null>(null)
  const [status, setStatus] = useState<'idle' | 'uploading' | 'success' | 'error'>('idle')
  const [error, setError] = useState<string | null>(null)

  if (!isOpen) return null

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (selectedFile) {
      setFile(selectedFile)
      setStatus('idle')
      setError(null)
    }
  }

  const handleImport = async () => {
    if (!file) return

    setStatus('uploading')
    setError(null)

    try {
      // Simulate upload for demo mode
      await new Promise((resolve) => setTimeout(resolve, 1500))
      setStatus('success')
      onImportComplete?.()
      setTimeout(() => {
        onClose()
        setFile(null)
        setStatus('idle')
      }, 1500)
    } catch {
      setStatus('error')
      setError('Failed to import file. Please try again.')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" role="dialog" aria-modal="true" aria-labelledby="import-modal-title">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-zinc-900 rounded-xl border border-zinc-700 shadow-2xl w-full max-w-md mx-4">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-zinc-700">
          <h2 id="import-modal-title" className="text-lg font-semibold text-white">Import Historical Data</h2>
          <button
            onClick={onClose}
            className="p-1 text-zinc-400 hover:text-white rounded-lg hover:bg-zinc-800"
            aria-label="Close dialog"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="p-4">
          <p className="text-sm text-zinc-400 mb-4">
            Upload a JSON or JSONL file containing trace data from your agent framework.
          </p>

          {/* File drop zone */}
          <label
            className={`flex flex-col items-center justify-center p-8 border-2 border-dashed rounded-lg cursor-pointer transition-colors ${
              file
                ? 'border-blue-500 bg-blue-500/10'
                : 'border-zinc-600 hover:border-zinc-500 hover:bg-zinc-800/50'
            }`}
          >
            <input
              type="file"
              className="hidden"
              accept=".json,.jsonl"
              onChange={handleFileChange}
              disabled={status === 'uploading'}
            />
            {file ? (
              <>
                <FileJson size={32} className="text-blue-400 mb-2" />
                <span className="text-sm text-white font-medium">{file.name}</span>
                <span className="text-xs text-zinc-400 mt-1">
                  {(file.size / 1024).toFixed(1)} KB
                </span>
              </>
            ) : (
              <>
                <Upload size={32} className="text-zinc-400 mb-2" />
                <span className="text-sm text-zinc-300">
                  Drag & drop or click to browse
                </span>
                <span className="text-xs text-zinc-500 mt-1">
                  Supports JSON and JSONL files
                </span>
              </>
            )}
          </label>

          {/* Status messages */}
          {status === 'success' && (
            <div className="flex items-center gap-2 mt-4 p-3 bg-green-500/10 border border-green-500/30 rounded-lg">
              <CheckCircle size={16} className="text-green-400" />
              <span className="text-sm text-green-400">Import successful!</span>
            </div>
          )}

          {status === 'error' && error && (
            <div className="flex items-center gap-2 mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
              <AlertCircle size={16} className="text-red-400" />
              <span className="text-sm text-red-400">{error}</span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-4 border-t border-zinc-700">
          <Button variant="ghost" onClick={onClose} disabled={status === 'uploading'}>
            Cancel
          </Button>
          <Button
            onClick={handleImport}
            disabled={!file || status === 'uploading' || status === 'success'}
            isLoading={status === 'uploading'}
          >
            Import
          </Button>
        </div>
      </div>
    </div>
  )
}
