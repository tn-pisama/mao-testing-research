'use client'

import { Card } from '../ui/Card'

export function QuickStart() {
  return (
    <section className="py-16">
      <h2 className="text-2xl font-bold text-white mb-6 text-center">Quick Start</h2>
      <Card>
        <div className="p-6">
          <pre className="text-sm text-zinc-300 bg-zinc-900 p-4 rounded-lg overflow-x-auto">
            <code>pip install mao-testing</code>
          </pre>
        </div>
      </Card>
    </section>
  )
}
