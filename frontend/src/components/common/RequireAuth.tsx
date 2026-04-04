'use client'

import { useSession } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { useEffect, type ReactNode } from 'react'

function hasDevBypass(): boolean {
  if (process.env.NODE_ENV === 'development' && process.env.NEXT_PUBLIC_DEV_API_KEY) {
    return true
  }
  if (typeof window !== 'undefined' && sessionStorage.getItem('pisama_impersonate_token')) {
    return true
  }
  return false
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useSession()
  const router = useRouter()
  const devBypass = hasDevBypass()

  useEffect(() => {
    if (!devBypass && status === 'unauthenticated') {
      router.replace('/sign-in')
    }
  }, [status, router, devBypass])

  if (devBypass) {
    return <>{children}</>
  }

  if (status === 'loading') {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="animate-pulse text-zinc-400">Loading...</div>
      </div>
    )
  }

  if (status === 'unauthenticated') {
    return null
  }

  return <>{children}</>
}
