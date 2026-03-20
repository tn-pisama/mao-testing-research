import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'LangGraph Integration',
  description: 'Integrate Pisama with LangGraph. Detect recursion, state corruption, edge misrouting, and checkpoint issues.',
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
