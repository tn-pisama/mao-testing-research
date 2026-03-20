import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Failure Modes',
  description: 'Complete reference for all 42 agent failure modes detected by Pisama. MAST taxonomy classification.',
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
