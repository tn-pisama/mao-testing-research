'use client'

export function FeatureCards() {
  return (
    <section className="py-16 max-w-6xl mx-auto px-8">
      <div className="grid md:grid-cols-3 gap-8">
        <div className="border border-neutral-200 p-8 bg-white">
          <h3 className="text-lg font-semibold text-black mb-4">Loop Detection</h3>
          <p className="text-sm text-neutral-600 leading-relaxed">
            Detect infinite loops in agent workflows
          </p>
        </div>
        <div className="border border-neutral-200 p-8 bg-white">
          <h3 className="text-lg font-semibold text-black mb-4">State Analysis</h3>
          <p className="text-sm text-neutral-600 leading-relaxed">
            Track and analyze agent state changes
          </p>
        </div>
        <div className="border border-neutral-200 p-8 bg-white">
          <h3 className="text-lg font-semibold text-black mb-4">Fix Suggestions</h3>
          <p className="text-sm text-neutral-600 leading-relaxed">
            AI-powered fix recommendations
          </p>
        </div>
      </div>
    </section>
  )
}
