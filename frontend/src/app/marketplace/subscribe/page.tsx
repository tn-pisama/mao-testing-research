'use client'

export const dynamic = 'force-dynamic'

import { useEffect, useState, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Shield, Loader2, CheckCircle2, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1'

type Status = 'resolving' | 'success' | 'error'

interface SubscribeResult {
  tenant_id: string
  tier: string
  message: string
}

function SubscribeContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [status, setStatus] = useState<Status>('resolving')
  const [result, setResult] = useState<SubscribeResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const token = searchParams.get('token') || searchParams.get('x-amzn-marketplace-token')
    if (!token) {
      setStatus('error')
      setError('No marketplace registration token found. Please subscribe through AWS Marketplace.')
      return
    }

    async function resolveSubscription(registrationToken: string) {
      try {
        const resp = await fetch(`${API_BASE}/marketplace/subscribe`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ registration_token: registrationToken }),
        })

        if (!resp.ok) {
          const body = await resp.json().catch(() => ({ detail: 'Unknown error' }))
          throw new Error(body.detail || `Subscription failed (${resp.status})`)
        }

        const data: SubscribeResult = await resp.json()
        setResult(data)
        setStatus('success')
      } catch (e: any) {
        setError(e.message || 'Failed to resolve marketplace subscription')
        setStatus('error')
      }
    }

    resolveSubscription(token)
  }, [searchParams])

  return (
    <>
      {status === 'resolving' && (
        <Card className="border-zinc-800 bg-zinc-900">
          <CardContent className="p-8 flex flex-col items-center gap-4 text-center">
            <Loader2 className="w-12 h-12 text-blue-400 animate-spin" />
            <h2 className="text-xl font-semibold text-zinc-100">
              Setting Up Your Account
            </h2>
            <p className="text-zinc-400">
              Verifying your AWS Marketplace subscription...
            </p>
          </CardContent>
        </Card>
      )}

      {status === 'success' && result && (
        <Card className="border-zinc-800 bg-zinc-900">
          <CardContent className="p-8 flex flex-col items-center gap-4 text-center">
            <CheckCircle2 className="w-16 h-16 text-green-500" />
            <h2 className="text-xl font-semibold text-zinc-100">
              Subscription Activated
            </h2>
            <p className="text-zinc-400">{result.message}</p>
            <div className="bg-zinc-800 rounded-lg px-4 py-2 text-sm text-zinc-300">
              Plan: <span className="font-medium text-blue-400 capitalize">{result.tier}</span>
            </div>
            <Button
              onClick={() => router.push('/onboarding')}
              className="w-full mt-2"
            >
              Get Started
            </Button>
          </CardContent>
        </Card>
      )}

      {status === 'error' && (
        <Card className="border-zinc-800 bg-zinc-900">
          <CardContent className="p-8 flex flex-col items-center gap-4 text-center">
            <AlertCircle className="w-16 h-16 text-red-500" />
            <h2 className="text-xl font-semibold text-zinc-100">
              Subscription Error
            </h2>
            <p className="text-red-400 text-sm">{error}</p>
            <div className="flex gap-3 w-full mt-2">
              <Button
                variant="secondary"
                onClick={() => window.location.reload()}
                className="flex-1"
              >
                Retry
              </Button>
              <Button
                onClick={() => router.push('/')}
                className="flex-1"
              >
                Go Home
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </>
  )
}

export default function MarketplaceSubscribePage() {
  return (
    <div className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center p-8">
      <div className="max-w-md w-full space-y-6">
        <div className="flex items-center justify-center gap-2 mb-8">
          <Shield className="h-10 w-10 text-blue-500" />
          <span className="text-2xl font-bold text-white">PISAMA</span>
        </div>

        <Suspense
          fallback={
            <Card className="border-zinc-800 bg-zinc-900">
              <CardContent className="p-8 flex flex-col items-center gap-4 text-center">
                <Loader2 className="w-12 h-12 text-blue-400 animate-spin" />
                <p className="text-zinc-400">Loading...</p>
              </CardContent>
            </Card>
          }
        >
          <SubscribeContent />
        </Suspense>

        <p className="text-xs text-zinc-600 text-center">
          Need help? Contact support@pisama.ai
        </p>
      </div>
    </div>
  )
}
