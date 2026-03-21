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
      if (account && user) {
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
