import { NextRequest, NextResponse } from 'next/server'
import { SignJWT, importPKCS8 } from 'jose'

const NOTIFY_EMAIL = 'tuomo@pisama.ai'
const SENDER_EMAIL = 'tuomo@pisama.ai'

async function getGmailAccessToken(): Promise<string | null> {
  const saKey = process.env.GOOGLE_SA_KEY
  if (!saKey) return null

  try {
    const sa = JSON.parse(saKey)
    const privateKey = await importPKCS8(sa.private_key, 'RS256')

    const now = Math.floor(Date.now() / 1000)
    const jwt = await new SignJWT({
      iss: sa.client_email,
      sub: SENDER_EMAIL,
      scope: 'https://www.googleapis.com/auth/gmail.send',
      aud: 'https://oauth2.googleapis.com/token',
      iat: now,
      exp: now + 3600,
    })
      .setProtectedHeader({ alg: 'RS256', typ: 'JWT' })
      .sign(privateKey)

    const tokenRes = await fetch('https://oauth2.googleapis.com/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: `grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer&assertion=${jwt}`,
    })

    const tokenData = await tokenRes.json()
    return tokenData.access_token || null
  } catch (err) {
    console.error('[WAITLIST] Failed to get Gmail token:', err)
    return null
  }
}

async function sendGmail(accessToken: string, to: string, subject: string, body: string) {
  const raw = btoa(
    `From: Pisama <${SENDER_EMAIL}>\r\n` +
    `To: ${to}\r\n` +
    `Subject: ${subject}\r\n` +
    `Content-Type: text/plain; charset=utf-8\r\n\r\n` +
    body
  ).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')

  await fetch('https://gmail.googleapis.com/gmail/v1/users/me/messages/send', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ raw }),
  })
}

export async function POST(request: NextRequest) {
  try {
    const { email } = await request.json()

    if (!email || !email.includes('@')) {
      return NextResponse.json({ error: 'Valid email is required' }, { status: 400 })
    }

    console.log(`[WAITLIST] ${new Date().toISOString()} — ${email}`)

    // Try Gmail API via service account
    const accessToken = await getGmailAccessToken()
    if (accessToken) {
      // Notify admin
      await sendGmail(
        accessToken,
        NOTIFY_EMAIL,
        `Waitlist signup: ${email}`,
        `New waitlist signup:\n\nEmail: ${email}\nTime: ${new Date().toISOString()}`
      )

      // Confirm to user
      await sendGmail(
        accessToken,
        email,
        'Welcome to the Pisama waitlist',
        `Thanks for joining the Pisama waitlist!\n\nWe'll let you know when we're ready for you.\n\n— The Pisama Team`
      )

      return NextResponse.json({ success: true })
    }

    // Fallback: try Resend
    const resendKey = process.env.RESEND_API_KEY
    if (resendKey) {
      await fetch('https://api.resend.com/emails', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${resendKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          from: 'Pisama <noreply@pisama.ai>',
          to: NOTIFY_EMAIL,
          subject: `Waitlist signup: ${email}`,
          text: `New waitlist signup:\n\nEmail: ${email}\nTime: ${new Date().toISOString()}`,
        }),
      })
      return NextResponse.json({ success: true })
    }

    // No email service — still return success (logged above)
    return NextResponse.json({ success: true })
  } catch (err) {
    console.error('[WAITLIST] Error:', err)
    return NextResponse.json({ error: 'Failed to process request' }, { status: 500 })
  }
}
