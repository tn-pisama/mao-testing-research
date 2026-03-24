import { NextRequest, NextResponse } from 'next/server'
import { getToken } from 'next-auth/jwt'

const BACKEND_URL = (process.env.NEXT_PUBLIC_API_URL || 'https://mao-api.fly.dev/api/v1').trim().replace(/^http:\/\//, 'https://')

export async function POST(request: NextRequest) {
  try {
    const token = await getToken({ req: request, secret: process.env.NEXTAUTH_SECRET })

    if (!token?.idToken) {
      return NextResponse.json({ error: 'No ID token' }, { status: 401 })
    }

    // Exchange Google ID token for a long-lived backend JWT
    const res = await fetch(`${BACKEND_URL}/auth/exchange-google-token`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token.idToken}` },
    })

    if (res.ok) {
      const data = await res.json()
      return NextResponse.json({
        access_token: data.access_token,
        tenant_id: data.tenant_id,
      })
    }

    const err = await res.text()
    console.error('[exchange-token] Backend error:', res.status, err)
    return NextResponse.json({ error: 'Token exchange failed' }, { status: res.status })
  } catch (err) {
    console.error('[exchange-token] Error:', err)
    return NextResponse.json({ error: 'Internal error' }, { status: 500 })
  }
}
