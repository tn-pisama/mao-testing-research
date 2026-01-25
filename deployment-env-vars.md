# Environment Variables for Google OAuth Deployment

## Generated Secrets

**NEXTAUTH_SECRET**: `O1a7nYdTSgevRPB1ATSjYwf77eR+BmGmW7HyLktS37M=`

**NEXTAUTH_URL**: `https://pisama.ai`

## Google OAuth Credentials (to be filled)

**GOOGLE_CLIENT_ID**: `[paste from Google Cloud Console]`

**GOOGLE_CLIENT_SECRET**: `[paste from Google Cloud Console]`

---

## Deployment Info

- Frontend: Vercel @ https://pisama.ai
- Backend: Fly.io @ https://mao-api.fly.dev (currently suspended)
- Database: Fly.io @ mao-db

## OAuth Redirect URIs Configured

- Production: https://pisama.ai/api/auth/callback/google
- Development: http://localhost:3000/api/auth/callback/google
