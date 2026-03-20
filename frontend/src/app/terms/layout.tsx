import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Terms of Service',
  description: 'Pisama terms of service and privacy policy.',
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
