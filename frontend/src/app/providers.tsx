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

    // localStorage cache disabled — was hydrating stale data with old tenant
    if (typeof window !== 'undefined') {
      try { localStorage.removeItem(CACHE_KEY) } catch {}
    }

    return client
  })

  // localStorage cache persistence disabled — was hydrating stale tenant data
  // SSR + TanStack Query staleTime handles caching instead

  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <UserPreferencesProvider>{children}</UserPreferencesProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}
