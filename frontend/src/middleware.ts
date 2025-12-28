import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server'
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

const isProtectedRoute = createRouteMatcher([
  '/dashboard(.*)',
  '/agents(.*)',
  '/traces(.*)',
  '/detections(.*)',
  '/settings(.*)',
  '/demo(.*)',
  '/review(.*)',
  '/testing(.*)',
])

const isPublicRoute = createRouteMatcher([
  '/',
  '/sign-in(.*)',
  '/sign-up(.*)',
  '/docs(.*)',
])

export default clerkMiddleware(async (auth, req) => {
  try {
    if (isPublicRoute(req)) {
      return NextResponse.next()
    }
    
    const { userId } = await auth()
    
    if (isProtectedRoute(req) && !userId) {
      const signInUrl = new URL('/', req.url)
      return NextResponse.redirect(signInUrl)
    }
    
    return NextResponse.next()
  } catch (error) {
    console.error('Middleware auth error:', error)
    return NextResponse.next()
  }
})

export const config = {
  matcher: [
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
  ],
}
