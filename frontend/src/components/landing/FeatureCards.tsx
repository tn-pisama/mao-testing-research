'use client'

export function FeatureCards() {
  return (
    <section className="py-4">
      <div className="grid md:grid-cols-3 gap-2">
        <div className="border border-zinc-800 bg-zinc-950 p-4">
          <h3 className="text-sm font-semibold text-white mb-1">{'[LOOP_DETECT]'}</h3>
          <p className="text-xs text-zinc-400">
            {'INFINITE_LOOP_DETECTION_IN_WORKFLOWS'}
          </p>
        </div>
        <div className="border border-zinc-800 bg-zinc-950 p-4">
          <h3 className="text-sm font-semibold text-white mb-1">{'[STATE_ANALYSIS]'}</h3>
          <p className="text-xs text-zinc-400">
            {'TRACK_AND_ANALYZE_AGENT_STATE_CHANGES'}
          </p>
        </div>
        <div className="border border-zinc-800 bg-zinc-950 p-4">
          <h3 className="text-sm font-semibold text-white mb-1">{'[FIX_SUGGEST]'}</h3>
          <p className="text-xs text-zinc-400">
            {'AI_POWERED_FIX_RECOMMENDATIONS'}
          </p>
        </div>
      </div>
    </section>
  )
}
