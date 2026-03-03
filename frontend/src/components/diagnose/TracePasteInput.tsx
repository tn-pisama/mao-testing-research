'use client'

import { Card } from '../ui/Card'

interface TracePasteInputProps {
  value?: string
  onChange?: (value: string) => void
  format?: string
  onFormatChange?: (format: string) => void
  disabled?: boolean
  onSubmit?: (trace: string) => void
}

export function TracePasteInput({
  value,
  onChange,
  format,
  onFormatChange,
  disabled,
  onSubmit,
}: TracePasteInputProps) {
  return (
    <Card>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <label className="text-sm font-medium text-zinc-200">
            Paste Trace Data
          </label>
          {format !== undefined && onFormatChange && (
            <select
              value={format}
              onChange={(e) => onFormatChange(e.target.value)}
              className="px-3 py-1 text-sm bg-zinc-700 border border-zinc-600 rounded-lg text-zinc-200"
              disabled={disabled}
            >
              <option value="json">JSON</option>
              <option value="otel">OpenTelemetry</option>
              <option value="langchain">LangChain</option>
            </select>
          )}
        </div>
        <textarea
          value={value || ''}
          onChange={(e) => onChange?.(e.target.value)}
          placeholder="Paste your trace data here..."
          className="w-full h-48 px-4 py-3 bg-zinc-800 border border-zinc-700 rounded-lg text-zinc-200 placeholder-zinc-500 font-mono text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
          disabled={disabled}
        />
        <p className="text-xs text-zinc-500">
          Supports JSON, OpenTelemetry, and LangChain trace formats
        </p>
      </div>
    </Card>
  )
}
