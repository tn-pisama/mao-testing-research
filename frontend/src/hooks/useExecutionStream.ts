import { useEffect, useState, useCallback } from 'react'
import { useSafeAuth } from './useSafeAuth'
import { useTenant } from './useTenant'

export interface ExecutionEvent {
  type: string
  trace_id: string
  execution_id: string
  workflow_id: string
  workflow_name: string
  status: string
  started_at?: string
  finished_at?: string
}

interface UseExecutionStreamProps {
  onExecution: (event: ExecutionEvent) => void
  enabled?: boolean
}

/**
 * Hook to stream real-time execution events via Server-Sent Events (SSE).
 *
 * Connects to the backend SSE endpoint and receives execution events as they happen.
 * Handles automatic reconnection on disconnect.
 *
 * @param onExecution - Callback function called when a new execution event is received
 * @param enabled - Whether the stream should be active (default: true)
 * @returns Object containing connection status
 *
 * @example
 * ```tsx
 * const { isConnected } = useExecutionStream({
 *   onExecution: (event) => {
 *     console.log('New execution:', event);
 *   }
 * });
 * ```
 */
export function useExecutionStream({ onExecution, enabled = true }: UseExecutionStreamProps) {
  const { getToken } = useSafeAuth()
  const { tenantId } = useTenant()
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const connect = useCallback(async () => {
    if (!tenantId || !enabled) {
      return
    }

    try {
      const token = await getToken()
      if (!token) {
        setError('No authentication token')
        return
      }

      // Construct SSE endpoint URL
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const url = `${baseUrl}/api/v1/n8n/stream`

      // EventSource doesn't support custom headers, so we use query param for auth
      const eventSource = new EventSource(url, {
        withCredentials: true,
      })

      eventSource.onopen = () => {
        console.log('[SSE] Connection opened')
        setIsConnected(true)
        setError(null)
      }

      eventSource.onerror = (err) => {
        console.error('[SSE] Connection error:', err)
        setIsConnected(false)
        setError('Connection lost')
        eventSource.close()

        // Attempt reconnect after 3 seconds
        setTimeout(() => {
          if (enabled) {
            connect()
          }
        }, 3000)
      }

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)

          // Handle different event types
          if (data.type === 'connected') {
            console.log('[SSE] Subscribed to channel:', data.channel)
          } else if (data.type === 'error') {
            console.error('[SSE] Server error:', data.message)
            setError(data.message)
          } else if (data.type === 'execution.created') {
            // Call the callback with the execution event
            onExecution(data as ExecutionEvent)
          }
        } catch (err) {
          console.error('[SSE] Failed to parse event data:', err)
        }
      }

      // Return cleanup function
      return () => {
        console.log('[SSE] Closing connection')
        eventSource.close()
      }
    } catch (err) {
      console.error('[SSE] Failed to connect:', err)
      setError('Failed to connect')
      setIsConnected(false)
    }
  }, [tenantId, enabled, getToken, onExecution])

  useEffect(() => {
    if (!enabled) {
      setIsConnected(false)
      return
    }

    const cleanup = connect()

    return () => {
      if (cleanup) {
        cleanup.then(fn => fn?.())
      }
    }
  }, [connect, enabled])

  return { isConnected, error }
}
