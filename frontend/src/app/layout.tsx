import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import { ClerkProvider } from '@clerk/nextjs'
import './globals.css'
import { Providers } from './providers'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'MAO Testing Platform',
  description: 'Catch AI agent failures before they cost you. Detect infinite loops, state corruption, persona drift, and coordination failures in your LLM agent systems.',
}

const hasClerk = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const content = (
    <html lang="en">
      <body className={inter.className}>
        <Providers>{children}</Providers>
      </body>
    </html>
  )

  if (!hasClerk) {
    return content
  }

  return (
    <ClerkProvider
      publishableKey={process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY!}
    >
      {content}
    </ClerkProvider>
  )
}
