import { NextRequest, NextResponse } from 'next/server'
import { getToken } from 'next-auth/jwt'

const BACKEND_URL = (process.env.NEXT_PUBLIC_API_URL || 'https://mao-api.fly.dev/api/v1').trim().replace(/^http:\/\//, 'https://')

export async function GET(request: NextRequest) {
  try {
    const token = await getToken({ req: request, secret: process.env.NEXTAUTH_SECRET })

    if (!token?.email) {
      console.log('[tenant] No email in token. Token keys:', token ? Object.keys(token) : 'null')
      console.log('[tenant] NEXTAUTH_SECRET set:', !!process.env.NEXTAUTH_SECRET)

      // Fallback: try to get email from Authorization header (Google ID token)
      const authHeader = request.headers.get('Authorization')
      if (authHeader?.startsWith('Bearer ')) {
        try {
          // Decode JWT payload without verification to get email
          const jwt = authHeader.slice(7)
          const payload = JSON.parse(Buffer.from(jwt.split('.')[1], 'base64').toString())
          if (payload.email) {
            console.log('[tenant] Got email from auth header:', payload.email)
            const res = await fetch(
              `${BACKEND_URL}/auth/tenant-by-email?email=${encodeURIComponent(payload.email)}`,
            )
            if (res.ok) {
              const data = await res.json()
              return NextResponse.json({ tenantId: data.tenant_id || 'default' })
            }
          }
        } catch {
          // Token might not be a JWT with email (e.g., backend JWT)
        }
      }

      return NextResponse.json({ tenantId: 'default' })
    }

    const res = await fetch(
      `${BACKEND_URL}/auth/tenant-by-email?email=${encodeURIComponent(token.email as string)}`,
    )

    if (res.ok) {
      const data = await res.json()
      return NextResponse.json({ tenantId: data.tenant_id || 'default' })
    }

    return NextResponse.json({ tenantId: 'default' })
  } catch (err) {
    console.error('[tenant] Error:', err)
    return NextResponse.json({ tenantId: 'default' })
  }
}
