'use client'

import { Card, CardTitle } from '../ui/Card'

export function FeatureCards() {
  return (
    <section className="py-16">
      <div className="grid md:grid-cols-3 gap-6">
        <Card>
          <div className="p-6">
            <CardTitle>Loop Detection</CardTitle>
            <p className="text-sm text-white/70 mt-2">Detect infinite loops in agent workflows</p>
          </div>
        </Card>
        <Card>
          <div className="p-6">
            <CardTitle>State Analysis</CardTitle>
            <p className="text-sm text-white/70 mt-2">Track and analyze agent state changes</p>
          </div>
        </Card>
        <Card>
          <div className="p-6">
            <CardTitle>Fix Suggestions</CardTitle>
            <p className="text-sm text-white/70 mt-2">AI-powered fix recommendations</p>
          </div>
        </Card>
      </div>
    </section>
  )
}
