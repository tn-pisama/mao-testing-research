import { NextRequest, NextResponse } from 'next/server'
import { getToken } from 'next-auth/jwt'

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'https://mao-api.fly.dev/api/v1'

export async function POST(request: NextRequest) {
  try {
    const token = await getToken({ req: request, secret: process.env.NEXTAUTH_SECRET })

    if (!token?.accessToken) {
      return NextResponse.json({ error: 'No backend token' }, { status: 401 })
    }

    const res = await fetch(`${BACKEND_URL}/auth/refresh`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token.accessToken}` },
    })

    if (res.ok) {
      const data = await res.json()
      return NextResponse.json({
        access_token: data.access_token,
        tenant_id: data.tenant_id,
      })
    }

    return NextResponse.json({ error: 'Refresh failed' }, { status: res.status })
  } catch (err) {
    console.error('[refresh-token] Error:', err)
    return NextResponse.json({ error: 'Internal error' }, { status: 500 })
  }
}
