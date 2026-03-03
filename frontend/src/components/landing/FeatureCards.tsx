'use client'

export function FeatureCards() {
  return (
    <section className="py-4">
      <div className="grid md:grid-cols-3 gap-2">
        <div className="border border-[#00ff00] bg-black p-4 relative scanline">
          <h3 className="text-sm font-semibold text-[#00ff00] mb-1">{'[LOOP_DETECT]'}</h3>
          <p className="text-xs text-[#00ff00] opacity-70">
            {'INFINITE_LOOP_DETECTION_IN_WORKFLOWS'}
          </p>
        </div>
        <div className="border border-[#00ff00] bg-black p-4 relative scanline">
          <h3 className="text-sm font-semibold text-[#00ff00] mb-1">{'[STATE_ANALYSIS]'}</h3>
          <p className="text-xs text-[#00ff00] opacity-70">
            {'TRACK_AND_ANALYZE_AGENT_STATE_CHANGES'}
          </p>
        </div>
        <div className="border border-[#00ff00] bg-black p-4 relative scanline">
          <h3 className="text-sm font-semibold text-[#00ff00] mb-1">{'[FIX_SUGGEST]'}</h3>
          <p className="text-xs text-[#00ff00] opacity-70">
            {'AI_POWERED_FIX_RECOMMENDATIONS'}
          </p>
        </div>
      </div>
    </section>
  )
}
