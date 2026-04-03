import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { getToken } from 'next-auth/jwt'

const publicRoutes = ['/', '/sign-in', '/sign-up', '/login']

function isPublicRoute(pathname: string): boolean {
  return publicRoutes.some(route => pathname === route || pathname.startsWith(route + '/'))
}

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl

  // Redirect /docs to /docs/ so MkDocs relative asset paths resolve correctly
  if (pathname === '/docs') {
    return NextResponse.redirect(new URL('/docs/', req.url))
  }

  // Public routes always pass through — no auth check needed
  if (isPublicRoute(pathname)) {
    return NextResponse.next()
  }

  // Everything else requires authentication
  try {
    const token = await getToken({
      req,
      secret: process.env.NEXTAUTH_SECRET
    })

    if (!token) {
      const signInUrl = new URL('/sign-in', req.url)
      return NextResponse.redirect(signInUrl)
    }

    return NextResponse.next()
  } catch (error) {
    console.error('Middleware auth error:', error)
    const signInUrl = new URL('/sign-in', req.url)
    return NextResponse.redirect(signInUrl)
  }
}

export const config = {
  matcher: [
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
  ],
}
