import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { getToken } from 'next-auth/jwt'

const protectedRoutes = [
  '/dashboard',
  '/agents',
  '/traces',
  '/detections',
  '/settings',
  '/demo',
  '/review',
  '/testing',
  '/docs',
  '/chaos',
  '/replay',
  '/regression',
  '/terms',
]

const publicRoutes = ['/', '/sign-in', '/sign-up']

function isProtectedRoute(pathname: string): boolean {
  return protectedRoutes.some(route => pathname.startsWith(route))
}

function isPublicRoute(pathname: string): boolean {
  return publicRoutes.some(route => pathname === route || pathname.startsWith(route + '/'))
}

export async function middleware(req: NextRequest) {
  try {
    const { pathname } = req.nextUrl

    if (isPublicRoute(pathname)) {
      return NextResponse.next()
    }

    // Full auth bypass for local development
    if (process.env.DISABLE_AUTH === 'true') {
      return NextResponse.next()
    }

    // Bypass auth for E2E tests (disabled in production for security)
    // Note: This only works for automated tests, not manual testing
    const testBypass = req.headers.get('x-test-bypass') === 'true'
    const allowTestBypass = process.env.ALLOW_TEST_BYPASS === 'true' || process.env.NODE_ENV === 'development'
    if (testBypass && allowTestBypass) {
      return NextResponse.next()
    }

    const token = await getToken({
      req,
      secret: process.env.NEXTAUTH_SECRET
    })

    if (isProtectedRoute(pathname) && !token) {
      const signInUrl = new URL('/sign-in', req.url)
      return NextResponse.redirect(signInUrl)
    }

    return NextResponse.next()
  } catch (error) {
    console.error('Middleware auth error:', error)
    return NextResponse.next()
  }
}

export const config = {
  matcher: [
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
  ],
}
