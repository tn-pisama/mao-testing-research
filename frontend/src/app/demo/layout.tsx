import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Demo',
  description: 'Try Pisama with sample data. See failure detection and self-healing in action.',
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
