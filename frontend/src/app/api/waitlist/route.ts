import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'https://mao-api.fly.dev/api/v1'
const NOTIFY_EMAIL = 'tuomo@pisama.ai'

export async function POST(request: NextRequest) {
  try {
    const { email } = await request.json()

    if (!email || !email.includes('@')) {
      return NextResponse.json({ error: 'Valid email is required' }, { status: 400 })
    }

    // 1. Try Resend if configured
    const resendKey = process.env.RESEND_API_KEY
    if (resendKey) {
      // Notify admin
      await fetch('https://api.resend.com/emails', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${resendKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          from: 'Pisama <noreply@pisama.ai>',
          to: NOTIFY_EMAIL,
          subject: `Waitlist signup: ${email}`,
          text: `New waitlist signup:\n\nEmail: ${email}\nTime: ${new Date().toISOString()}`,
        }),
      })

      // Confirm to user
      await fetch('https://api.resend.com/emails', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${resendKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          from: 'Pisama <noreply@pisama.ai>',
          to: email,
          subject: 'Welcome to the Pisama waitlist',
          text: `Thanks for joining the Pisama waitlist!\n\nWe'll let you know when we're ready for you.\n\n— The Pisama Team`,
        }),
      })

      return NextResponse.json({ success: true })
    }

    // 2. Fallback: store in backend database via webhook
    try {
      await fetch(`${BACKEND_URL}/webhooks/waitlist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, timestamp: new Date().toISOString() }),
      }).catch(() => {})
    } catch {
      // Best-effort
    }

    // 3. Always log
    console.log(`[WAITLIST] ${new Date().toISOString()} — ${email}`)

    return NextResponse.json({ success: true })
  } catch {
    return NextResponse.json({ error: 'Failed to process request' }, { status: 500 })
  }
}
