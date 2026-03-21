import { ImageResponse } from 'next/og'

export const runtime = 'edge'
export const alt = 'Pisama - Agent Forensics Platform'
export const size = { width: 1200, height: 630 }
export const contentType = 'image/png'

export default async function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          background: '#09090b',
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'relative',
        }}
      >
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: 4,
            background: '#3b82f6',
          }}
        />
        <div
          style={{
            fontSize: 72,
            fontWeight: 700,
            color: '#ffffff',
            marginBottom: 16,
          }}
        >
          Pisama
        </div>
        <div
          style={{
            fontSize: 32,
            color: '#a1a1aa',
            marginBottom: 32,
          }}
        >
          Agent Forensics Platform
        </div>
        <div
          style={{
            fontSize: 22,
            color: '#71717a',
          }}
        >
          Detect and fix failures in multi-agent AI systems
        </div>
      </div>
    ),
    { ...size }
  )
}
