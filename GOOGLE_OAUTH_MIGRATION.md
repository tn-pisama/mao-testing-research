# Google OAuth Migration Guide

This guide walks you through migrating from Clerk to native Google OAuth with NextAuth.js.

## Overview

**Status**: ✅ Code Migration Complete
**Remaining**: Environment setup and database migration

The codebase has been updated to use Google OAuth via NextAuth.js. Both Clerk and Google OAuth are supported during the migration period for backward compatibility.

---

## Prerequisites

Before starting, you need:

1. Google OAuth credentials (see Step 1 below)
2. Database access to run migrations
3. Environment variable access in your deployment platform

---

## Step 1: Create Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Select your project or create a new one
3. Navigate to **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
4. Configure OAuth consent screen if prompted:
   - User Type: External
   - Add required info (app name, support email, etc.)
5. For Application type, select **Web application**
6. Add **Authorized redirect URIs**:
   - Development: `http://localhost:3000/api/auth/callback/google`
   - Production: `https://your-domain.com/api/auth/callback/google`
7. Click **Create** and save the:
   - `Client ID` (starts with: `xxx.apps.googleusercontent.com`)
   - `Client Secret` (starts with: `GOCSPX-xxx`)

---

## Step 2: Update Environment Variables

### Frontend (.env.local)

```bash
# Google OAuth (NextAuth)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your-client-secret

# NextAuth Configuration
# Generate secret with: openssl rand -base64 32
NEXTAUTH_SECRET=your-random-32-character-secret-here
NEXTAUTH_URL=http://localhost:3000  # Change to production URL in production

# Backend API URL
NEXT_PUBLIC_API_URL=http://localhost:8000  # Or your backend URL
```

### Backend (.env)

```bash
# Google OAuth
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your-client-secret

# Keep existing JWT_SECRET and other settings...
```

### Deployment Platforms

**Vercel (Frontend)**:
1. Go to Project Settings → Environment Variables
2. Add the variables listed above
3. Redeploy

**Render/Railway (Backend)**:
1. Go to Environment → Environment Variables
2. Add `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`
3. Redeploy

---

## Step 3: Run Database Migration

The migration adds the `google_user_id` column and makes `clerk_user_id` nullable.

### Local Development

```bash
cd backend
alembic upgrade head
```

### Production

**Render**:
```bash
# SSH into your instance or run via dashboard
alembic upgrade head
```

**Railway**:
```bash
railway run alembic upgrade head
```

---

## Step 4: Test Authentication Flow

1. **Start local development**:
   ```bash
   # Terminal 1: Backend
   cd backend
   uvicorn app.main:app --reload

   # Terminal 2: Frontend
   cd frontend
   npm run dev
   ```

2. **Test sign-in**:
   - Navigate to `http://localhost:3000/sign-in`
   - Click "Continue with Google"
   - Sign in with your Google account
   - Should redirect to `/dashboard`

3. **Verify backend authentication**:
   - Open browser DevTools → Network tab
   - Make an authenticated API call
   - Check that `Authorization` header contains the Google ID token
   - Backend should log: `auth_success_google`

---

## Step 5: Migration Strategy

### Option A: Clean Cutover (Recommended for New Projects)

1. Set up Google OAuth credentials
2. Update environment variables
3. Run database migration
4. Deploy frontend + backend simultaneously
5. Existing users will need to sign in again with Google

**Pros**: Clean, simple
**Cons**: Existing users must re-authenticate

### Option B: Gradual Migration (For Production Systems)

The backend supports both Clerk and Google OAuth simultaneously.

1. Deploy backend with Google OAuth support (keeps Clerk working)
2. Run database migration
3. Deploy frontend with Google OAuth
4. Existing Clerk users can continue using Clerk
5. New users use Google OAuth
6. Users who sign in with Google (using same email) are auto-migrated
7. Once all users migrated, remove Clerk credentials

**Pros**: No user disruption
**Cons**: More complex deployment

---

## Architecture Changes

### Frontend

| File | Change |
|------|--------|
| `package.json` | Added `next-auth@^4.24.0` |
| `src/app/api/auth/[...nextauth]/route.ts` | **NEW** - NextAuth configuration with Google provider |
| `src/app/layout.tsx` | Replaced `ClerkProvider` with `SessionProvider` |
| `src/middleware.ts` | Replaced `clerkMiddleware` with NextAuth `getToken` |
| `src/hooks/useSafeAuth.ts` | Now uses `useSession` from NextAuth |
| `src/hooks/useTenant.ts` | Fetches tenant from backend API instead of Clerk metadata |
| `src/app/sign-in/[[...sign-in]]/page.tsx` | Custom Google sign-in button (replaces Clerk UI) |

### Backend

| File | Change |
|------|--------|
| `app/core/google_auth.py` | **NEW** - Google ID token verification |
| `app/core/dependencies.py` | Updated to support both Clerk and Google OAuth |
| `app/config.py` | Added `google_client_id` and `google_client_secret` |
| `app/storage/models.py` | Added `google_user_id` column to User model |
| `alembic/versions/20250124_add_google_oauth.py` | **NEW** - Database migration |

---

## Backward Compatibility

### What Still Works

- ✅ Clerk authentication (if credentials are set)
- ✅ API Key authentication
- ✅ Existing database schema

### What's New

- ✅ Google OAuth authentication
- ✅ Automatic user migration (by email)
- ✅ Tenant auto-creation for new Google users

### Migration Behavior

When a user signs in with Google:

1. Backend checks if user exists with `google_user_id`
2. If not found, checks if user exists with same email
3. If found by email, updates user with `google_user_id` (migration)
4. If not found at all, creates new user + tenant

---

## Troubleshooting

### Error: "Invalid Google token"

- Check that `GOOGLE_CLIENT_ID` matches in frontend and backend
- Verify redirect URI is correct in Google Console
- Check that token hasn't expired

### Error: "User not associated with any organization"

- This shouldn't happen with Google OAuth (auto-creates tenant)
- May occur if database migration wasn't run
- Check backend logs for details

### Frontend: Sign-in redirects to Clerk

- Check that `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` is NOT set
- Clear browser cache/cookies
- Rebuild frontend: `npm run build && npm start`

### Backend: 401 Unauthorized

- Check that `GOOGLE_CLIENT_ID` is set in backend
- Verify ID token is being sent in `Authorization: Bearer <token>` header
- Check backend logs for token verification errors

---

## Next Steps

1. ✅ Code changes complete
2. ⏳ Set up Google OAuth credentials
3. ⏳ Update environment variables
4. ⏳ Run database migration
5. ⏳ Test authentication flow
6. ⏳ Deploy to production
7. ⏳ (Optional) Remove Clerk package after full migration

---

## Rollback Plan

If you need to rollback:

1. Revert environment variables to Clerk
2. Deploy previous version of code
3. Run database downgrade: `alembic downgrade -1`

---

## Cost Savings

| Service | Before | After | Savings |
|---------|--------|-------|---------|
| Clerk | $25-$99/mo | $0 | $300-$1,200/year |
| Google OAuth | $0 | $0 | - |

**Total Savings**: $300-$1,200/year
