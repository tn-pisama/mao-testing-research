'use client'

import { Card } from '../ui/Card'

export function TraceUpload({ onUpload }: { onUpload?: (file: File) => void }) {
  return (
    <Card>
      <div className="text-center py-8 text-slate-400">
        <p className="text-sm">Trace upload coming soon</p>
      </div>
    </Card>
  )
}
