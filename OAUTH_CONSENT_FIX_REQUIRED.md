# OAuth Consent Screen Fix Required

## 🔍 Problem Identified

Your OAuth client is correctly configured, but the **OAuth consent screen** (also called "brand") is set to **"Internal"** which only allows users in your Google Workspace organization to sign in.

For public authentication (anyone with a Google account), it needs to be **"External"**.

## Current Configuration

```json
{
  "applicationTitle": "ai-discovery",
  "name": "projects/434388095406/brands/434388095406",
  "orgInternalOnly": true,  ← THIS IS THE PROBLEM
  "supportEmail": "tuomo@pisama.ai"
}
```

## ❌ Why Automated Fix Failed

Google **does not provide an API** to:
- Change consent screen from Internal to External
- Delete and recreate the consent screen
- Update the `orgInternalOnly` field

This configuration **MUST** be changed manually through the Google Cloud Console.

---

## ✅ Manual Fix (2-3 minutes)

I've opened the OAuth consent screen page in your browser:
https://console.cloud.google.com/apis/credentials/consent?project=ai-discovery-469923

### Step 1: Change User Type to External

Look for one of these options:

**Option A**: If you see a "MAKE EXTERNAL" button:
- Click **"MAKE EXTERNAL"**
- Confirm the change

**Option B**: If you see "EDIT APP":
- Click **"EDIT APP"**
- Change **User Type** from "Internal" to "External"
- Click **"SAVE"**

### Step 2: Configure App Information

Fill in the following fields:

| Field | Value |
|-------|-------|
| **App name** | `PISAMA` |
| **User support email** | `tuomo@pisama.ai` |
| **App logo** | (optional - skip) |
| **Application home page** | `https://pisama.ai` |
| **Application privacy policy** | `https://pisama.ai/privacy` (or skip) |
| **Application terms of service** | `https://pisama.ai/terms` (or skip) |
| **Authorized domains** | Click "ADD DOMAIN" → `pisama.ai` |
| **Developer contact** | `tuomo@pisama.ai` |

Click **"SAVE AND CONTINUE"**

### Step 3: Configure Scopes

1. Click **"ADD OR REMOVE SCOPES"**
2. In the filter/search box, find and check these scopes:
   - ✅ `.../auth/userinfo.email` - See your email address
   - ✅ `.../auth/userinfo.profile` - See your personal info
   - ✅ `openid` - Associate you with your personal info
3. Click **"UPDATE"**
4. Click **"SAVE AND CONTINUE"**

### Step 4: Add Test Users (IMPORTANT)

**Note**: External apps start in "Testing" mode. You need to add yourself as a test user.

1. Click **"+ ADD USERS"**
2. Enter: `tuomo@pisama.ai`
3. Click **"ADD"**
4. Click **"SAVE AND CONTINUE"**

### Step 5: Review and Finish

1. Review the summary page
2. Click **"BACK TO DASHBOARD"**

---

## 🧪 Verify the Fix

After completing the above steps, run this command:

```bash
./verify-oauth-fix.sh
```

It will check that:
- ✅ OAuth consent screen is External (not Internal)
- ✅ OAuth client exists
- ✅ Vercel environment variables are set

Then test at: **https://pisama.ai/sign-in**

---

## 📝 Publishing Status

After the fix, your app will be in **"Testing"** mode:

- **Testing Mode**:
  - Only test users (tuomo@pisama.ai) can sign in
  - Good for initial testing
  - No Google verification required

- **To Make Public Later** (optional):
  - Go to OAuth consent screen
  - Click "PUBLISH APP"
  - Submit for Google verification (can take weeks)
  - OR keep in Testing mode and manually add users

For now, **Testing mode is fine** - just make sure your email is added as a test user.

---

## ❓ Troubleshooting

### Still see "Error 401: invalid_client"?

1. **Verify consent screen is External**:
   ```bash
   gcloud alpha iap oauth-brands list --project=ai-discovery-469923 --format=json
   ```
   Should show: `"orgInternalOnly": false`

2. **Verify test user is added**:
   - Go to OAuth consent screen
   - Check "Test users" section
   - Confirm `tuomo@pisama.ai` is listed

3. **Clear browser cache**:
   - Sign out of Google completely
   - Clear browser cookies for google.com
   - Try again

4. **Try incognito mode**:
   - Open incognito/private window
   - Go to https://pisama.ai/sign-in
   - Try signing in with tuomo@pisama.ai

---

## 🎯 Summary

**What's working**:
- ✅ OAuth 2.0 Web Application client created
- ✅ Client ID and Secret configured in Vercel & Fly.io
- ✅ Frontend code configured with NextAuth.js
- ✅ Backend ready to verify Google tokens

**What needs fixing**:
- ❌ OAuth consent screen set to Internal → needs to be External
- ❌ Test user needs to be added (tuomo@pisama.ai)

**Time required**: 2-3 minutes of manual configuration

**After the fix**: Authentication should work immediately at https://pisama.ai/sign-in

---

**When you're done**, reply here and I'll verify everything is working!
