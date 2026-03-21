import { NextRequest, NextResponse } from 'next/server'
import { getToken } from 'next-auth/jwt'

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'https://mao-api.fly.dev/api/v1'

export async function GET(request: NextRequest) {
  try {
    // Get the NextAuth JWT which contains the Google ID token
    const token = await getToken({ req: request, secret: process.env.NEXTAUTH_SECRET })

    if (!token?.idToken) {
      return NextResponse.json({ tenantId: 'default' })
    }

    // Forward the Google ID token to the backend
    // The backend's get_current_user_or_tenant checks iss=accounts.google.com
    const res = await fetch(`${BACKEND_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${token.idToken}` },
    })

    if (res.ok) {
      const data = await res.json()
      return NextResponse.json({ tenantId: data.tenant_id || data.tenantId || 'default' })
    }

    // If /auth/me fails (Clerk check), try extracting tenant from the token directly
    // The backend returns tenant_id in error responses sometimes
    return NextResponse.json({ tenantId: 'default' })
  } catch {
    return NextResponse.json({ tenantId: 'default' })
  }
}
