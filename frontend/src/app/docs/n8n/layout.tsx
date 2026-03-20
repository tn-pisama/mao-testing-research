import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'n8n Integration',
  description: 'Integrate Pisama with n8n workflows. Detect cycles, schema mismatches, timeout issues, and resource limits.',
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
