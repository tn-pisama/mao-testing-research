import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import { Analytics } from '@vercel/analytics/react'
import { Toaster } from 'sonner'
import { GoogleAnalytics } from '@next/third-parties/google'
import './globals.css'
import { Providers } from './providers'
import { SessionWrapper } from '../components/SessionWrapper'

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' })

export const metadata: Metadata = {
  title: { default: 'Pisama - Agent Forensics', template: '%s | Pisama' },
  description: 'Detect and fix failures in multi-agent AI systems. 42 detectors for loops, state corruption, persona drift, and more. Open source.',
  metadataBase: new URL('https://pisama.ai'),
  openGraph: {
    title: 'Pisama - Agent Forensics',
    description: 'Detect and fix failures in multi-agent AI systems. Self-healing diagnostics with root cause analysis.',
    url: 'https://pisama.ai',
    siteName: 'Pisama',
    type: 'website',
    locale: 'en_US',
    images: [{ url: '/og-image.svg', width: 1200, height: 630, alt: 'Pisama - Agent Forensics Platform' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Pisama - Agent Forensics',
    description: 'Detect and fix failures in multi-agent AI systems.',
    images: ['/og-image.svg'],
  },
  robots: { index: true, follow: true },
  keywords: ['AI agent testing', 'multi-agent failure detection', 'LLM observability', 'agent forensics', 'self-healing AI', 'LangGraph', 'CrewAI', 'AutoGen'],
  authors: [{ name: 'Pisama' }],
  creator: 'Pisama',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const gaId = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID

  return (
    <html lang="en">
      <body className={`${inter.variable} font-sans`}>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              '@context': 'https://schema.org',
              '@type': 'SoftwareApplication',
              name: 'Pisama',
              description: 'Multi-agent failure detection and self-healing platform for AI systems.',
              applicationCategory: 'DeveloperApplication',
              operatingSystem: 'Web',
              url: 'https://pisama.ai',
              offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
              author: { '@type': 'Organization', name: 'Pisama', url: 'https://pisama.ai' },
            }),
          }}
        />
        <SessionWrapper>
          <Providers>{children}</Providers>
        </SessionWrapper>
        <Analytics />
        <Toaster
          theme="dark"
          position="bottom-right"
          toastOptions={{
            style: {
              background: '#1e293b',
              border: '1px solid #334155',
              color: '#f1f5f9',
            },
          }}
        />
        {gaId && <GoogleAnalytics gaId={gaId} />}
      </body>
    </html>
  )
}
