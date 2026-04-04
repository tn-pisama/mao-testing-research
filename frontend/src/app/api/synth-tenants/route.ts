import { NextResponse } from 'next/server'

const BACKEND = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

export async function GET() {
  try {
    const res = await fetch(`${BACKEND}/auth/synth-tenants`, { cache: 'no-store' })
    const data = await res.json()
    return NextResponse.json(data)
  } catch (err) {
    return NextResponse.json({ tenants: [], error: String(err) }, { status: 502 })
  }
}

export async function POST(req: Request) {
  try {
    const { tenantId } = await req.json()
    const res = await fetch(`${BACKEND}/auth/synth-tenants/${tenantId}/impersonate`, {
      method: 'POST',
    })
    const data = await res.json()
    return NextResponse.json(data)
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 502 })
  }
}
