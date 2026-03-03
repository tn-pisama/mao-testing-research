'use client'

import { Wrench, CheckCircle, Clock, XCircle, ChevronRight } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card'
import Link from 'next/link'

interface FixesStatusCardProps {
  isLoading?: boolean
}

export function FixesStatusCard({ isLoading }: FixesStatusCardProps) {
  if (isLoading) {
    return (
      <Card>
        <div className="h-40 animate-pulse bg-zinc-700 rounded-lg" />
      </Card>
    )
  }

  // In a real app, these would come from API
  const fixStats = {
    applied: 12,
    pending: 3,
    rejected: 1,
    successRate: 92,
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Wrench className="h-5 w-5 text-purple-400" />
            Fixes Status
          </CardTitle>
          <Link
            href="/healing"
            className="flex items-center gap-1 text-sm text-blue-400 hover:text-blue-300"
          >
            Manage fixes
            <ChevronRight size={16} />
          </Link>
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex items-end gap-3 mb-4">
          <div className="text-4xl font-bold text-white">
            {fixStats.successRate}%
          </div>
          <div className="text-sm text-zinc-400 mb-1">
            success rate
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4 text-sm">
          <div className="flex items-center gap-2">
            <CheckCircle className="h-4 w-4 text-green-400" />
            <span className="text-zinc-400">Applied:</span>
            <span className="font-medium text-green-400">{fixStats.applied}</span>
          </div>
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-yellow-400" />
            <span className="text-zinc-400">Pending:</span>
            <span className="font-medium text-yellow-400">{fixStats.pending}</span>
          </div>
          <div className="flex items-center gap-2">
            <XCircle className="h-4 w-4 text-red-400" />
            <span className="text-zinc-400">Rejected:</span>
            <span className="font-medium text-red-400">{fixStats.rejected}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
