'use client'

import { Layout } from '@/components/common/Layout'
import { Button } from '@/components/ui/Button'
import { XCircle } from 'lucide-react'
import Link from 'next/link'

export default function BillingCancelPage() {
  return (
    <Layout>
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center max-w-md">
          <div className="flex justify-center mb-6">
            <div className="p-4 rounded-full bg-zinc-800 border border-zinc-700">
              <XCircle className="w-12 h-12 text-zinc-400" />
            </div>
          </div>
          <h1 className="text-2xl font-bold text-white mb-2">Payment Cancelled</h1>
          <p className="text-zinc-400 mb-8">
            Your plan has not been changed.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Link href="/billing">
              <Button variant="primary">
                Try Again
              </Button>
            </Link>
            <Link href="/dashboard">
              <Button variant="secondary">
                Go to Dashboard
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </Layout>
  )
}
