import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { getToken } from 'next-auth/jwt'

const protectedRoutes = [
  '/dashboard',
  '/agents',
  '/traces',
  '/detections',
  '/healing',
  '/quality',
  '/settings',
  '/account',
  '/evals',
  '/testing',
  '/chaos',
  '/replay',
  '/regression',
  '/security',
  '/memory',
  '/integrations',
  '/n8n',
  '/dify',
  '/langgraph',
  '/openclaw',
  '/diagnose',
  '/import',
  '/metrics',
  '/benchmarks',
  '/tools',
  '/review',
  '/detector-status',
  '/conversation-evaluations',
  '/docs',
]

const publicRoutes = ['/', '/sign-in', '/sign-up', '/login', '/terms', '/case-studies', '/onboarding', '/demo']

function isProtectedRoute(pathname: string): boolean {
  return protectedRoutes.some(route => pathname.startsWith(route))
}

function isPublicRoute(pathname: string): boolean {
  return publicRoutes.some(route => pathname === route || pathname.startsWith(route + '/'))
}

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl

  // Public routes always pass through — no auth check needed
  if (isPublicRoute(pathname)) {
    return NextResponse.next()
  }

  try {
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
    // Don't redirect to sign-in if we're already on a non-protected route
    if (isProtectedRoute(pathname)) {
      const signInUrl = new URL('/sign-in', req.url)
      return NextResponse.redirect(signInUrl)
    }
    return NextResponse.next()
  }
}

export const config = {
  matcher: [
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
  ],
}
