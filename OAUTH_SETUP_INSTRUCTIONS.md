# Google OAuth Setup - Manual Steps

I've opened the Google Cloud Console for you. Follow these exact steps:

## In the Google Cloud Console (Browser Window)

### Step 1: Create OAuth Client ID

1. You should see the "Create OAuth client ID" page
2. If you see "Configure Consent Screen" button, click it first:
   - User Type: **External**
   - Click **CREATE**
   - App name: **PISAMA**
   - User support email: **tuomo@pisama.ai**
   - Developer contact: **tuomo@pisama.ai**
   - Click **SAVE AND CONTINUE** through all steps
   - Click **BACK TO DASHBOARD**

3. Return to **Credentials** → **+ CREATE CREDENTIALS** → **OAuth client ID**

4. Fill in:
   - Application type: **Web application**
   - Name: **PISAMA Production**

5. Under **Authorized redirect URIs**, click **+ ADD URI** twice and add:
   ```
   https://pisama.ai/api/auth/callback/google
   ```
   ```
   http://localhost:3000/api/auth/callback/google
   ```

6. Click **CREATE**

7. A popup will show your credentials:
   - Copy the **Client ID** (looks like: `xxx-xxx.apps.googleusercontent.com`)
   - Copy the **Client secret** (looks like: `GOCSPX-xxxxx`)

### Step 2: Run the Automated Deployment

Once you have the credentials, run this in your terminal:

```bash
cd /Users/tuomonikulainen/mao-testing-research

./deploy-google-oauth.sh "YOUR_CLIENT_ID" "YOUR_CLIENT_SECRET"
```

Or without arguments (it will prompt you):

```bash
./deploy-google-oauth.sh
```

## What the Script Does

✅ Updates Vercel environment variables
✅ Updates Fly.io secrets
✅ Runs database migration
✅ Deploys frontend to production

## Estimated Time

- Manual OAuth setup: 2-3 minutes
- Automated script: 3-5 minutes
- **Total: ~5-8 minutes**

---

## Already Configured

✅ NEXTAUTH_SECRET: Generated (`O1a7nYdTSgevRPB1ATSjYwf77eR+BmGmW7HyLktS37M=`)
✅ NEXTAUTH_URL: Set to `https://pisama.ai`
✅ Redirect URIs: Configured for production and development
✅ Deployment scripts: Ready to run
