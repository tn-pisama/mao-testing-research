import { NextRequest, NextResponse } from 'next/server'
import { getToken } from 'next-auth/jwt'

import API_URL from '@/lib/api-url'

const BACKEND_URL = API_URL

export async function POST(request: NextRequest) {
  try {
    const token = await getToken({ req: request, secret: process.env.NEXTAUTH_SECRET })

    // Try JWT refresh first (if we have a backend token to refresh)
    if (token?.accessToken) {
      const res = await fetch(`${BACKEND_URL}/auth/refresh`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token.accessToken}` },
      })
      if (res.ok) return NextResponse.json(await res.json())
    }

    // Fallback: server-to-server token using email from NextAuth session
    const email = token?.email as string | undefined
    if (email && process.env.SERVER_AUTH_SECRET) {
      const res = await fetch(`${BACKEND_URL}/auth/server-token`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-server-secret': process.env.SERVER_AUTH_SECRET,
        },
        body: JSON.stringify({ email }),
      })
      if (res.ok) return NextResponse.json(await res.json())
    }

    return NextResponse.json({ error: 'Auth failed' }, { status: 401 })
  } catch (err) {
    console.error('[refresh-token] Error:', err)
    return NextResponse.json({ error: 'Internal error' }, { status: 500 })
  }
}
