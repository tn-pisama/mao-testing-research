import { NextRequest, NextResponse } from 'next/server'
import { getToken } from 'next-auth/jwt'

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'https://mao-api.fly.dev/api/v1'

export async function GET(request: NextRequest) {
  try {
    const token = await getToken({ req: request, secret: process.env.NEXTAUTH_SECRET })

    if (!token?.email) {
      return NextResponse.json({ tenantId: 'default' })
    }

    // Look up tenant by email (server-to-server, no token expiry issues)
    const res = await fetch(
      `${BACKEND_URL}/auth/tenant-by-email?email=${encodeURIComponent(token.email as string)}`,
    )

    if (res.ok) {
      const data = await res.json()
      return NextResponse.json({ tenantId: data.tenant_id || 'default' })
    }

    return NextResponse.json({ tenantId: 'default' })
  } catch {
    return NextResponse.json({ tenantId: 'default' })
  }
}
