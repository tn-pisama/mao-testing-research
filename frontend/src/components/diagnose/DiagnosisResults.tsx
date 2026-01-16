'use client'

import { Card } from '../ui/Card'

export function DiagnosisResults({ results, result }: { results?: unknown; result?: unknown }) {
  return (
    <Card>
      <div className="text-center py-8 text-slate-400">
        <p className="text-sm">Diagnosis results coming soon</p>
      </div>
    </Card>
  )
}
