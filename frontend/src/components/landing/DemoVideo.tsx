'use client'

import { Play } from 'lucide-react'
import { useState } from 'react'

export function DemoVideo() {
  const [isPlaying, setIsPlaying] = useState(false)

  // TODO: Replace with actual YouTube video ID when video is uploaded (PIS-W1-2-C-008)
  const videoId = '' // e.g., 'dQw4w9WgXcQ'

  return (
    <section className="py-20 px-4">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
            See PISAMA in Action
          </h2>
          <p className="text-slate-400 text-lg">
            Watch how PISAMA catches agent failures in 4 minutes
          </p>
        </div>

        <div className="relative aspect-video rounded-xl overflow-hidden border border-slate-700 bg-slate-900">
          {videoId && isPlaying ? (
            // YouTube embed when video is available and playing
            <iframe
              className="absolute inset-0 w-full h-full"
              src={`https://www.youtube.com/embed/${videoId}?autoplay=1`}
              title="PISAMA Demo Video"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
            />
          ) : (
            // Placeholder with play button
            <div
              className="absolute inset-0 flex items-center justify-center cursor-pointer group"
              onClick={() => setIsPlaying(true)}
            >
              {/* Background image/gradient */}
              <div className="absolute inset-0 bg-gradient-to-br from-slate-800 to-slate-900" />

              {/* Placeholder content */}
              <div className="relative z-10 text-center">
                <div className="w-20 h-20 rounded-full bg-sky-500 flex items-center justify-center mx-auto mb-4 group-hover:bg-sky-600 transition-colors">
                  <Play className="w-8 h-8 text-white ml-1" fill="currentColor" />
                </div>
                <p className="text-white font-semibold text-lg mb-2">
                  {videoId ? 'Watch Demo' : 'Demo Video Coming Soon'}
                </p>
                <p className="text-slate-400 text-sm">
                  {videoId ? '4 minute overview' : 'Subscribe to get notified when we launch'}
                </p>
              </div>

              {/* Screenshot placeholder overlay - replace with actual screenshot when available */}
              {!videoId && (
                <div className="absolute inset-0 bg-slate-800/80 backdrop-blur-sm" />
              )}
            </div>
          )}
        </div>

        {/* Key takeaways below video */}
        <div className="mt-8 grid md:grid-cols-3 gap-6">
          <div className="text-center">
            <div className="text-sky-400 font-bold text-lg mb-1">1 min</div>
            <div className="text-slate-400 text-sm">Integration setup</div>
          </div>
          <div className="text-center">
            <div className="text-sky-400 font-bold text-lg mb-1">2 min</div>
            <div className="text-slate-400 text-sm">Catching failures</div>
          </div>
          <div className="text-center">
            <div className="text-sky-400 font-bold text-lg mb-1">1 min</div>
            <div className="text-slate-400 text-sm">Fix recommendations</div>
          </div>
        </div>
      </div>
    </section>
  )
}
