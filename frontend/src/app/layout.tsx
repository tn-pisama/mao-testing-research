import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import { Analytics } from '@vercel/analytics/react'
import { GoogleAnalytics } from '@next/third-parties/google'
import './globals.css'
import { Providers } from './providers'
import { SessionWrapper } from '../components/SessionWrapper'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'PISAMA - Agent Forensics',
  description: 'Find out why your AI agent failed and how to fix it. Self-healing AI agent diagnostics with root cause analysis.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const gaId = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID

  return (
    <html lang="en">
      <body className={inter.className}>
        <SessionWrapper>
          <Providers>{children}</Providers>
        </SessionWrapper>
        <Analytics />
        {gaId && <GoogleAnalytics gaId={gaId} />}
      </body>
    </html>
  )
}
