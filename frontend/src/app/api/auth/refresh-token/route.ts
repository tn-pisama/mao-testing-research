import { NextRequest, NextResponse } from 'next/server'
import { getToken } from 'next-auth/jwt'

import API_URL from '@/lib/api-url'

const BACKEND_URL = API_URL

export async function POST(request: NextRequest) {
  try {
    const token = await getToken({ req: request, secret: process.env.NEXTAUTH_SECRET })
    const email = token?.email as string | undefined

    // Always use server-token (gets tenant from DB, not stale JWT)
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
