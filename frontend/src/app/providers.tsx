'use client'

import { QueryClient, QueryClientProvider, hydrate, dehydrate } from '@tanstack/react-query'
import { useState, useEffect, Component, ReactNode } from 'react'
import { UserPreferencesProvider } from '@/lib/user-preferences'

interface ErrorBoundaryState {
  hasError: boolean
  error?: Error
}

class ErrorBoundary extends Component<{ children: ReactNode; fallback?: ReactNode }, ErrorBoundaryState> {
  constructor(props: { children: ReactNode; fallback?: ReactNode }) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Application error:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <div className="min-h-screen bg-zinc-900 flex items-center justify-center p-4">
          <div className="bg-zinc-800 rounded-lg p-8 max-w-md text-center">
            <h2 className="text-xl font-semibold text-white mb-4">Something went wrong</h2>
            <p className="text-zinc-400 mb-6">
              An unexpected error occurred. Please refresh the page to try again.
            </p>
            <button
              onClick={() => window.location.reload()}
              className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg transition-colors"
            >
              Refresh Page
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

const TWENTY_FOUR_HOURS = 24 * 60 * 60 * 1000
const CACHE_KEY = 'pisama_query_cache'

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => {
    const client = new QueryClient({
      defaultOptions: {
        queries: {
          staleTime: 60 * 1000,
          gcTime: TWENTY_FOUR_HOURS,
          refetchOnWindowFocus: false,
        },
      },
    })

    // Hydrate from localStorage synchronously (client only)
    if (typeof window !== 'undefined') {
      try {
        const raw = localStorage.getItem(CACHE_KEY)
        if (raw) {
          const { timestamp, state } = JSON.parse(raw)
          if (Date.now() - timestamp < TWENTY_FOUR_HOURS) {
            hydrate(client, state)
          } else {
            localStorage.removeItem(CACHE_KEY)
          }
        }
      } catch {
        // Corrupt cache, ignore
      }
    }

    return client
  })

  // Persist cache on changes (debounced) and on tab hide
  useEffect(() => {
    if (typeof window === 'undefined') return

    let timeout: ReturnType<typeof setTimeout>

    function saveCache() {
      try {
        localStorage.setItem(CACHE_KEY, JSON.stringify({
          timestamp: Date.now(),
          state: dehydrate(queryClient),
        }))
      } catch {}
    }

    const unsubscribe = queryClient.getQueryCache().subscribe(() => {
      clearTimeout(timeout)
      timeout = setTimeout(saveCache, 2000)
    })

    const handleVisibility = () => {
      if (document.visibilityState === 'hidden') saveCache()
    }
    document.addEventListener('visibilitychange', handleVisibility)

    return () => {
      clearTimeout(timeout)
      unsubscribe()
      document.removeEventListener('visibilitychange', handleVisibility)
    }
  }, [queryClient])

  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <UserPreferencesProvider>{children}</UserPreferencesProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}
