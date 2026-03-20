import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'OpenClaw Integration',
  description: 'Integrate Pisama with OpenClaw. Detect session loops, tool abuse, sandbox escape, and spawn chains.',
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
