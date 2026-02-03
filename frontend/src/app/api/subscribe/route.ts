import { NextRequest, NextResponse } from 'next/server'
import { Resend } from 'resend'

const resend = new Resend(process.env.RESEND_API_KEY)

export async function POST(request: NextRequest) {
  try {
    const { email } = await request.json()

    // Validate email
    if (!email || !email.includes('@')) {
      return NextResponse.json(
        { error: 'Valid email is required' },
        { status: 400 }
      )
    }

    // Add to Resend audience (create audience in Resend dashboard first)
    const audienceId = process.env.RESEND_AUDIENCE_ID

    if (!audienceId) {
      console.error('RESEND_AUDIENCE_ID not configured')
      // Still return success to user, but log error internally
      return NextResponse.json({
        success: true,
        message: 'Thanks for signing up! We\'ll be in touch soon.',
      })
    }

    try {
      await resend.contacts.create({
        email,
        audienceId,
      })
    } catch (resendError: any) {
      // If contact already exists, that's ok
      if (resendError?.message?.includes('already exists')) {
        return NextResponse.json({
          success: true,
          message: 'You\'re already on the list!',
        })
      }
      throw resendError
    }

    // Send welcome email
    try {
      await resend.emails.send({
        from: 'PISAMA <onboarding@pisama.dev>',
        to: email,
        subject: 'Welcome to PISAMA - Your Agent Testing Platform',
        html: `
          <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
            <h1 style="color: #1a365d;">Welcome to PISAMA!</h1>
            <p>Thanks for signing up for early access to PISAMA - the multi-agent orchestration testing platform.</p>

            <h2 style="color: #0ea5e9;">What's Next?</h2>
            <ul>
              <li>We'll send you launch updates as we get closer to public beta</li>
              <li>You'll get early access to the platform (launching Q1 2026)</li>
              <li>Priority support during onboarding</li>
            </ul>

            <h2 style="color: #0ea5e9;">In the Meantime...</h2>
            <p>Check out our documentation to learn how PISAMA can help catch agent failures before production:</p>
            <p><a href="https://pisama.dev/docs" style="color: #0ea5e9;">Read the Docs →</a></p>

            <p style="margin-top: 32px; color: #64748b;">
              Questions? Reply to this email - we read every message.
            </p>

            <p style="color: #64748b;">
              — The PISAMA Team
            </p>
          </div>
        `,
      })
    } catch (emailError) {
      // Log but don't fail - contact was added successfully
      console.error('Failed to send welcome email:', emailError)
    }

    return NextResponse.json({
      success: true,
      message: 'Thanks for signing up! Check your email for next steps.',
    })
  } catch (error) {
    console.error('Subscription error:', error)
    return NextResponse.json(
      { error: 'Failed to process subscription. Please try again.' },
      { status: 500 }
    )
  }
}
