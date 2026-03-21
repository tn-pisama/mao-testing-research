import NextAuth, { NextAuthOptions } from 'next-auth'
import GoogleProvider from 'next-auth/providers/google'
import type { JWT } from 'next-auth/jwt'
import type { Session } from 'next-auth'

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
      // Initial sign in — exchange Google token for long-lived backend JWT
      if (account && user) {
        const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'https://mao-api.fly.dev/api/v1'

        try {
          const res = await fetch(`${backendUrl}/auth/exchange-google-token`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${account.id_token}` },
          })
          if (res.ok) {
            const data = await res.json()
            return {
              ...token,
              idToken: data.access_token, // Backend JWT (24h TTL)
              googleId: account.providerAccountId,
              tenantId: data.tenant_id,
            }
          }
        } catch {
          // Backend unavailable — fall back to Google token
        }

        return {
          ...token,
          idToken: account.id_token,
          googleId: account.providerAccountId,
        }
      }
      return token
    },
    async session({ session, token }: { session: Session; token: JWT }) {
      // Send properties to the client
      return {
        ...session,
        user: {
          ...session.user,
          id: token.sub,
          googleId: token.googleId,
        },
        idToken: token.idToken,
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

const handler = NextAuth(authOptions)

export { handler as GET, handler as POST }
