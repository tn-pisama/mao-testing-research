'use client'

import { Clipboard, FileText, FileCode } from 'lucide-react'
import { clsx } from 'clsx'

interface TracePasteInputProps {
  value: string
  onChange: (value: string) => void
  format: string
  onFormatChange: (format: string) => void
  disabled?: boolean
}

const FORMATS = [
  { value: 'auto', label: 'Auto-detect' },
  { value: 'langsmith', label: 'LangSmith' },
  { value: 'otel', label: 'OpenTelemetry' },
  { value: 'generic', label: 'Raw JSON' },
]

export function TracePasteInput({
  value,
  onChange,
  format,
  onFormatChange,
  disabled = false,
}: TracePasteInputProps) {
  const handlePaste = async () => {
    try {
      const text = await navigator.clipboard.readText()
      onChange(text)
    } catch (err) {
      console.error('Failed to read clipboard:', err)
    }
  }

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      const reader = new FileReader()
      reader.onload = (event) => {
        const content = event.target?.result as string
        onChange(content)
      }
      reader.readAsText(file)
    }
  }

  return (
    <div className="space-y-4">
      {/* Format Selector */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-slate-400">Format:</span>
        <div className="flex gap-1">
          {FORMATS.map((fmt) => (
            <button
              key={fmt.value}
              onClick={() => onFormatChange(fmt.value)}
              disabled={disabled}
              className={clsx(
                'px-3 py-1.5 text-sm rounded-lg transition-colors',
                format === fmt.value
                  ? 'bg-primary-600 text-white'
                  : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
              )}
            >
              {fmt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Text Area */}
      <div className="relative">
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          placeholder="Paste your trace JSON here, or upload a file..."
          className={clsx(
            'w-full h-80 p-4 bg-slate-900 border border-slate-700 rounded-xl',
            'text-slate-200 font-mono text-sm resize-none',
            'placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent',
            disabled && 'opacity-50 cursor-not-allowed'
          )}
        />

        {/* Overlay Actions */}
        {!value && !disabled && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="flex gap-4 pointer-events-auto">
              <button
                onClick={handlePaste}
                className="flex flex-col items-center gap-2 p-4 bg-slate-800 hover:bg-slate-700 rounded-xl border border-slate-600 border-dashed transition-colors"
              >
                <Clipboard className="w-8 h-8 text-primary-400" />
                <span className="text-sm text-slate-300">Paste from clipboard</span>
              </button>

              <label className="flex flex-col items-center gap-2 p-4 bg-slate-800 hover:bg-slate-700 rounded-xl border border-slate-600 border-dashed transition-colors cursor-pointer">
                <FileText className="w-8 h-8 text-primary-400" />
                <span className="text-sm text-slate-300">Upload file</span>
                <input
                  type="file"
                  accept=".json,.jsonl,.txt"
                  onChange={handleFileUpload}
                  className="hidden"
                />
              </label>
            </div>
          </div>
        )}
      </div>

      {/* Stats */}
      {value && (
        <div className="flex items-center gap-4 text-sm text-slate-400">
          <div className="flex items-center gap-1.5">
            <FileCode className="w-4 h-4" />
            <span>{value.length.toLocaleString()} characters</span>
          </div>
          <div>
            <span>{value.split('\n').length.toLocaleString()} lines</span>
          </div>
        </div>
      )}
    </div>
  )
}
