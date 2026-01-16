'use client'

import { Card } from '../ui/Card'

export function FeatureCards() {
  return (
    <section className="py-16">
      <div className="grid md:grid-cols-3 gap-6">
        <Card>
          <div className="p-6">
            <h3 className="text-lg font-semibold text-white mb-2">Loop Detection</h3>
            <p className="text-sm text-slate-400">Detect infinite loops in agent workflows</p>
          </div>
        </Card>
        <Card>
          <div className="p-6">
            <h3 className="text-lg font-semibold text-white mb-2">State Analysis</h3>
            <p className="text-sm text-slate-400">Track and analyze agent state changes</p>
          </div>
        </Card>
        <Card>
          <div className="p-6">
            <h3 className="text-lg font-semibold text-white mb-2">Fix Suggestions</h3>
            <p className="text-sm text-slate-400">AI-powered fix recommendations</p>
          </div>
        </Card>
      </div>
    </section>
  )
}
