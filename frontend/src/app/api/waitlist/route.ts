import { NextRequest, NextResponse } from 'next/server'

export async function POST(request: NextRequest) {
  try {
    const { email } = await request.json()

    if (!email || !email.includes('@')) {
      return NextResponse.json({ error: 'Valid email is required' }, { status: 400 })
    }

    // Send notification email via Resend if configured
    const resendKey = process.env.RESEND_API_KEY
    if (resendKey) {
      await fetch('https://api.resend.com/emails', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${resendKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          from: 'Pisama Waitlist <waitlist@pisama.ai>',
          to: 'tuomo@pisama.ai',
          subject: `Waitlist signup: ${email}`,
          text: `New waitlist signup:\n\nEmail: ${email}\nTime: ${new Date().toISOString()}`,
        }),
      })
    } else {
      // Fallback: log to console
      console.log(`[WAITLIST] New signup: ${email}`)
    }

    return NextResponse.json({ success: true })
  } catch {
    return NextResponse.json({ error: 'Failed to process request' }, { status: 500 })
  }
}
