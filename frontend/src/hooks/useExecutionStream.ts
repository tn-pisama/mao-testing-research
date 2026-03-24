import { useEffect, useState, useRef, useCallback } from 'react'
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

  // Use refs to keep latest values accessible without re-triggering the effect
  const onExecutionRef = useRef(onExecution)
  useEffect(() => {
    onExecutionRef.current = onExecution
  }, [onExecution])

  const getTokenRef = useRef(getToken)
  useEffect(() => {
    getTokenRef.current = getToken
  }, [getToken])

  const connect = useCallback(async (
    cancelled: { current: boolean },
    setEventSource: (es: EventSource | null) => void,
    scheduleReconnect: () => void,
  ) => {
    if (cancelled.current) return

    try {
      const token = await getTokenRef.current()
      if (!token || cancelled.current) {
        if (!cancelled.current) setError('No authentication token')
        return
      }

      // Construct SSE endpoint URL
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'https://mao-api.fly.dev'
      const url = `${baseUrl}/api/v1/n8n/stream`

      // EventSource doesn't support custom headers, so we use query param for auth
      const eventSource = new EventSource(url, {
        withCredentials: true,
      })
      setEventSource(eventSource)

      eventSource.onopen = () => {
        console.log('[SSE] Connection opened')
        if (!cancelled.current) {
          setIsConnected(true)
          setError(null)
        }
      }

      eventSource.onerror = (err) => {
        console.error('[SSE] Connection error:', err)
        if (!cancelled.current) {
          setIsConnected(false)
          setError('Connection lost')
        }
        eventSource.close()
        setEventSource(null)

        // Attempt reconnect after 3 seconds
        if (!cancelled.current) {
          scheduleReconnect()
        }
      }

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)

          // Handle different event types
          if (data.type === 'connected') {
            console.log('[SSE] Subscribed to channel:', data.channel)
          } else if (data.type === 'error') {
            console.error('[SSE] Server error:', data.message)
            if (!cancelled.current) setError(data.message)
          } else if (data.type === 'execution.created') {
            // Call the callback with the execution event
            onExecutionRef.current(data as ExecutionEvent)
          }
        } catch (err) {
          console.error('[SSE] Failed to parse event data:', err)
        }
      }
    } catch (err) {
      console.error('[SSE] Failed to connect:', err)
      if (!cancelled.current) {
        setError('Failed to connect')
        setIsConnected(false)
      }
    }
  }, [])

  useEffect(() => {
    if (!tenantId || !enabled) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional state reset when disabled
      setIsConnected(false)
      return
    }

    const cancelled = { current: false }
    let eventSource: EventSource | null = null
    let reconnectTimer: NodeJS.Timeout | null = null

    const setEventSource = (es: EventSource | null) => {
      eventSource = es
    }

    const scheduleReconnect = () => {
      reconnectTimer = setTimeout(() => {
        connect(cancelled, setEventSource, scheduleReconnect)
      }, 3000)
    }

    connect(cancelled, setEventSource, scheduleReconnect)

    return () => {
      cancelled.current = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
      if (eventSource) {
        console.log('[SSE] Closing connection')
        eventSource.close()
      }
    }
  }, [tenantId, enabled, connect])

  return { isConnected, error }
}
