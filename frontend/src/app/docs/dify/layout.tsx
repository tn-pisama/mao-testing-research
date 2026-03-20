import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Dify Integration',
  description: 'Integrate Pisama with Dify. Detect RAG poisoning, iteration escape, model fallback, and variable leaks.',
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
