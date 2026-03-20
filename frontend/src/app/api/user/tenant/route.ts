import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'https://mao-api.fly.dev/api/v1'

export async function GET(request: NextRequest) {
  try {
    const authHeader = request.headers.get('Authorization')
    if (!authHeader) {
      return NextResponse.json({ tenantId: 'default' })
    }

    const res = await fetch(`${BACKEND_URL}/auth/me`, {
      headers: { Authorization: authHeader },
    })

    if (res.ok) {
      const data = await res.json()
      return NextResponse.json({ tenantId: data.tenant_id || data.tenantId || 'default' })
    }

    return NextResponse.json({ tenantId: 'default' })
  } catch {
    return NextResponse.json({ tenantId: 'default' })
  }
}
