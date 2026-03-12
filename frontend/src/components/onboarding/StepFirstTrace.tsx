'use client'

import { useState, useEffect, useRef } from 'react'
import { CheckCircle2, Loader2, AlertCircle, Play } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import type { createApiClient } from '@/lib/api'

interface StepFirstTraceProps {
  apiClient: ReturnType<typeof createApiClient>
  onTraceReceived: (traceId: string) => void
  onSkipToDemo: () => void
}

export function StepFirstTrace({ apiClient, onTraceReceived, onSkipToDemo }: StepFirstTraceProps) {
  const [status, setStatus] = useState<'waiting' | 'received' | 'timeout' | 'error'>('waiting')
  const [traceInfo, setTraceInfo] = useState<{ id: string; count: number; at: string } | null>(null)
  const [showTroubleshoot, setShowTroubleshoot] = useState(false)
  const pollRef = useRef<NodeJS.Timeout | null>(null)
  const startRef = useRef(Date.now())

  useEffect(() => {
    const poll = async () => {
      try {
        const data = await apiClient.getOnboardingStatus()
        if (data.has_traces && data.first_trace_id) {
          setStatus('received')
          setTraceInfo({
            id: data.first_trace_id,
            count: data.trace_count,
            at: data.first_trace_at || new Date().toISOString(),
          })
          if (pollRef.current) clearInterval(pollRef.current)
          onTraceReceived(data.first_trace_id)
          return
        }
      } catch {
        // Ignore errors during polling — keep trying
      }

      // Check for timeout (5 minutes)
      if (Date.now() - startRef.current > 5 * 60 * 1000) {
        setStatus('timeout')
        if (pollRef.current) clearInterval(pollRef.current)
      }
    }

    // Poll every 3 seconds
    poll()
    pollRef.current = setInterval(poll, 3000)

    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [apiClient, onTraceReceived])

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-2xl font-bold text-zinc-100">Waiting for Your First Trace</h2>
        <p className="text-zinc-400 mt-2">
          Run your agent with the OTEL instrumentation, and we&apos;ll detect it here
        </p>
      </div>

      <Card className="border-zinc-800 bg-zinc-900">
        <CardContent className="p-8 flex flex-col items-center text-center gap-4">
          {status === 'waiting' && (
            <>
              <div className="relative">
                <div className="w-16 h-16 rounded-full bg-blue-500/20 flex items-center justify-center">
                  <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
                </div>
                <div className="absolute inset-0 rounded-full bg-blue-500/10 animate-ping" />
              </div>
              <p className="text-zinc-300 font-medium">Listening for traces...</p>
              <p className="text-sm text-zinc-500">
                Usually takes under a minute after running your agent
              </p>
            </>
          )}

          {status === 'received' && traceInfo && (
            <>
              <CheckCircle2 className="w-16 h-16 text-green-500" />
              <p className="text-zinc-100 font-semibold text-lg">Trace Received!</p>
              <div className="text-sm text-zinc-400 space-y-1">
                <p>Trace ID: <code className="text-zinc-300">{traceInfo.id.slice(0, 8)}...</code></p>
                <p>Total traces: {traceInfo.count}</p>
              </div>
            </>
          )}

          {status === 'timeout' && (
            <>
              <AlertCircle className="w-16 h-16 text-amber-500" />
              <p className="text-zinc-100 font-semibold">No traces received yet</p>
              <p className="text-sm text-zinc-400">
                It&apos;s been 5 minutes. You can troubleshoot or try the demo instead.
              </p>
              <Button
                variant="secondary"
                onClick={() => setShowTroubleshoot(!showTroubleshoot)}
                className="mt-2"
              >
                Troubleshoot
              </Button>
            </>
          )}
        </CardContent>
      </Card>

      {showTroubleshoot && (
        <Card className="border-zinc-800 bg-zinc-900">
          <CardContent className="p-4 text-sm text-zinc-400 space-y-2">
            <p className="font-medium text-zinc-200">Common Issues:</p>
            <ul className="list-disc list-inside space-y-1">
              <li>Check that the OTEL exporter endpoint URL is correct</li>
              <li>Verify your API key is set in the Authorization header</li>
              <li>Make sure your agent is actually running and producing traces</li>
              <li>Check firewall/network settings allow outbound HTTPS</li>
              <li>For n8n/Dify: verify the webhook node is connected and enabled</li>
            </ul>
          </CardContent>
        </Card>
      )}

      <Button
        variant="secondary"
        onClick={onSkipToDemo}
        className="w-full border-zinc-700 text-zinc-400 hover:text-zinc-200"
      >
        <Play className="w-4 h-4 mr-2" />
        Skip with Demo Data
      </Button>
    </div>
  )
}
