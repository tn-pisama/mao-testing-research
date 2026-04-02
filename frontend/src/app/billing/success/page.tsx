'use client'

import { Layout } from '@/components/common/Layout'
import { Button } from '@/components/ui/Button'
import { CheckCircle } from 'lucide-react'
import Link from 'next/link'

export default function BillingSuccessPage() {
  return (
    <Layout>
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center max-w-md">
          <div className="flex justify-center mb-6">
            <div className="p-4 rounded-full bg-green-500/10 border border-green-500/20">
              <CheckCircle className="w-12 h-12 text-green-400" />
            </div>
          </div>
          <h1 className="text-2xl font-bold text-white mb-2">Payment Successful</h1>
          <p className="text-zinc-400 mb-8">
            Your plan has been upgraded. It may take a moment for changes to take effect.
          </p>
          <Link href="/dashboard">
            <Button variant="primary" size="lg">
              Go to Dashboard
            </Button>
          </Link>
        </div>
      </div>
    </Layout>
  )
}
