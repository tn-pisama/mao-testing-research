'use client'

import { Card } from '../ui/Card'
import { Upload } from 'lucide-react'

export function TraceUpload({ onUpload }: { onUpload?: (file: File) => void }) {
  return (
    <Card>
      <div className="text-center py-12 text-white/60 font-mono">
        <Upload size={32} className="mx-auto mb-3 opacity-50" />
        <p className="text-sm">Drop trace files here</p>
        <p className="text-xs mt-1 text-white/40">Supports OTEL, n8n, and custom formats</p>
      </div>
    </Card>
  )
}
