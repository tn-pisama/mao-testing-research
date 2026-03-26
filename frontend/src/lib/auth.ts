import type { NextAuthOptions } from 'next-auth'
import GoogleProvider from 'next-auth/providers/google'
import CredentialsProvider from 'next-auth/providers/credentials'
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
    CredentialsProvider({
      name: 'Email',
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) return null

        const res = await fetch(`${BACKEND_URL}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: credentials.email,
            password: credentials.password,
          }),
        })

        if (!res.ok) return null

        const data = await res.json()
        return {
          id: data.user_id,
          email: credentials.email,
          accessToken: data.access_token,
          tenantId: data.tenant_id,
        }
      },
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
      // Credentials provider: user object carries the backend token
      if (user && (user as any).accessToken) {
        token.accessToken = (user as any).accessToken
        token.tenantId = (user as any).tenantId
        token.backendTokenExpiry = Date.now() + 23 * 60 * 60 * 1000
        return token
      }

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
