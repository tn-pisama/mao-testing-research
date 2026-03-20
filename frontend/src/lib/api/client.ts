export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

export interface FetchOptions {
  method?: string
  body?: unknown
  headers?: Record<string, string>
  token?: string | null
  tenantId?: string | null
}

export interface ApiError extends Error {
  status: number
}

export async function fetchApi<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const { token, tenantId } = options

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...options.headers,
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const url = endpoint.includes('{tenant_id}') && tenantId
    ? `${API_BASE}${endpoint.replace('{tenant_id}', tenantId)}`
    : `${API_BASE}${endpoint}`

  const response = await fetch(url, {
    method: options.method || 'GET',
    headers,
    credentials: 'include',
    body: options.body ? JSON.stringify(options.body) : undefined,
  })

  if (!response.ok) {
    let detail = `API Error: ${response.status}`
    try {
      const body = await response.json()
      if (body.detail) detail = body.detail
    } catch {
      // non-JSON response, keep status-only message
    }

    // Handle auth errors with redirect
    if (response.status === 401 && typeof window !== 'undefined') {
      console.warn('Unauthorized — redirecting to login')
      window.location.href = '/login'
    }

    const err = new Error(detail) as ApiError
    err.status = response.status
    throw err
  }

  return response.json()
}
