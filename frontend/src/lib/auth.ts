import type { NextAuthOptions } from 'next-auth'
import GoogleProvider from 'next-auth/providers/google'
import type { JWT } from 'next-auth/jwt'
import type { Session } from 'next-auth'

import API_URL from '@/lib/api-url'

const BACKEND_URL = API_URL

export const authOptions: NextAuthOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID || '',
      clientSecret: process.env.GOOGLE_CLIENT_SECRET || '',
    }),
  ],
  callbacks: {
    async signIn({ account, profile }) {
      if (account?.provider === 'google') {
        const allowedEmails = (process.env.ALLOWED_EMAILS || '').split(',').map(e => e.trim()).filter(Boolean)
        if (allowedEmails.length > 0 && !allowedEmails.includes(profile?.email || '')) {
          return false
        }
      }
      return true
    },
    async jwt({ token, account, user }) {
      // Initial sign-in: exchange Google token for backend JWT
      if (account && user) {
        token.idToken = account.id_token
        token.googleId = account.providerAccountId

        try {
          const res = await fetch(`${BACKEND_URL}/auth/exchange-google-token`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${account.id_token}` },
          })
          if (res.ok) {
            const data = await res.json()
            token.accessToken = data.access_token
            token.tenantId = data.tenant_id
            token.backendTokenExpiry = Date.now() + 23 * 60 * 60 * 1000
          }
        } catch (err) {
          console.warn('[nextauth] Backend token exchange failed:', err)
        }
      }

      // Subsequent requests: refresh if expired or expiring within 1 hour
      if (token.accessToken && !account) {
        const expiry = (token.backendTokenExpiry as number) || 0
        const expiresIn = expiry - Date.now()
        if (expiresIn < 60 * 60 * 1000) {
          try {
            const ctrl = new AbortController()
            const t = setTimeout(() => ctrl.abort(), 3000)
            const res = await fetch(`${BACKEND_URL}/auth/refresh`, {
              method: 'POST',
              headers: { Authorization: `Bearer ${token.accessToken}` },
              signal: ctrl.signal,
            })
            clearTimeout(t)
            if (res.ok) {
              const data = await res.json()
              token.accessToken = data.access_token
              token.tenantId = data.tenant_id
              token.backendTokenExpiry = Date.now() + 23 * 60 * 60 * 1000
            }
          } catch {
            // Refresh failed — token stays as-is, client will retry
          }
        }
      }

      return token
    },
    async session({ session, token }: { session: Session; token: JWT }) {
      return {
        ...session,
        user: {
          ...session.user,
          id: token.sub,
          googleId: token.googleId,
        },
        idToken: token.idToken,
        accessToken: token.accessToken,
        tenantId: token.tenantId,
      }
    },
  },
  pages: {
    signIn: '/sign-in',
  },
  session: {
    strategy: 'jwt',
  },
  secret: process.env.NEXTAUTH_SECRET,
}
