import { NextRequest, NextResponse } from 'next/server'
import crypto from 'crypto'

const NOTIFY_EMAIL = 'tuomo@pisama.ai'
const SENDER_EMAIL = 'tuomo@pisama.ai'

function base64url(data: string | Buffer): string {
  return Buffer.from(data).toString('base64url')
}

function createJWT(sa: { client_email: string; private_key: string }): string {
  const header = base64url(JSON.stringify({ alg: 'RS256', typ: 'JWT' }))
  const now = Math.floor(Date.now() / 1000)
  const payload = base64url(JSON.stringify({
    iss: sa.client_email,
    sub: SENDER_EMAIL,
    scope: 'https://www.googleapis.com/auth/gmail.send',
    aud: 'https://oauth2.googleapis.com/token',
    iat: now,
    exp: now + 3600,
  }))

  const signInput = `${header}.${payload}`
  const signature = crypto.sign('RSA-SHA256', Buffer.from(signInput), sa.private_key)

  return `${signInput}.${base64url(signature)}`
}

async function getGmailAccessToken(): Promise<string | null> {
  const saKey = process.env.GOOGLE_SA_KEY
  if (!saKey) return null

  try {
    const sa = JSON.parse(saKey)
    const jwt = createJWT(sa)

    const res = await fetch('https://oauth2.googleapis.com/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: `grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer&assertion=${jwt}`,
    })

    const data = await res.json()
    if (!res.ok) {
      console.error('[WAITLIST] Token error:', JSON.stringify(data))
      return null
    }
    return data.access_token || null
  } catch (err) {
    console.error('[WAITLIST] JWT error:', err)
    return null
  }
}

async function sendGmail(accessToken: string, to: string, subject: string, body: string): Promise<boolean> {
  const message = [
    `From: Pisama <${SENDER_EMAIL}>`,
    `To: ${to}`,
    `Subject: ${subject}`,
    'Content-Type: text/plain; charset=utf-8',
    '',
    body,
  ].join('\r\n')

  const raw = Buffer.from(message).toString('base64url')

  const res = await fetch('https://gmail.googleapis.com/gmail/v1/users/me/messages/send', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ raw }),
  })

  if (!res.ok) {
    const err = await res.text()
    console.error('[WAITLIST] Gmail send error:', err)
    return false
  }
  return true
}

export async function POST(request: NextRequest) {
  try {
    const { email } = await request.json()

    if (!email || !email.includes('@')) {
      return NextResponse.json({ error: 'Valid email is required' }, { status: 400 })
    }

    console.log(`[WAITLIST] ${new Date().toISOString()} — ${email}`)

    const accessToken = await getGmailAccessToken()
    if (accessToken) {
      const notifySent = await sendGmail(
        accessToken,
        NOTIFY_EMAIL,
        `Waitlist signup: ${email}`,
        `New waitlist signup:\n\nEmail: ${email}\nTime: ${new Date().toISOString()}`
      )

      const confirmSent = await sendGmail(
        accessToken,
        email,
        'Welcome to the Pisama waitlist',
        `Thanks for joining the Pisama waitlist!\n\nWe'll let you know when we're ready for you.\n\n— The Pisama Team`
      )

      console.log(`[WAITLIST] Notify: ${notifySent}, Confirm: ${confirmSent}`)
      return NextResponse.json({ success: true })
    }

    console.log('[WAITLIST] No email service configured, signup logged only')
    return NextResponse.json({ success: true })
  } catch (err) {
    console.error('[WAITLIST] Error:', err)
    return NextResponse.json({ error: 'Failed to process request' }, { status: 500 })
  }
}
