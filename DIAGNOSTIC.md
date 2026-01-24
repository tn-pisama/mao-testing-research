# Frontend Data Diagnostic

## Current Situation

You're seeing:
- ✅ **Detections page**: Has data
- ❌ **Traces page**: Empty
- ❌ **n8n page**: Empty

## Likely Cause

The pages behave differently based on API response:

### Detections Page
- **If API fails**: Falls back to demo data (20+ detections)
- **If API succeeds but empty**: Shows 0 detections
- **You see data** → Likely showing **demo data** (API failed)

### Traces Page
- **If API fails**: Falls back to demo data (10+ traces)
- **If API succeeds but empty**: Shows "no traces" message
- **You see empty** → API succeeded, but **database is empty**

### n8n Page
- **If API fails**: Shows error
- **If API succeeds but empty**: Shows "No workflows registered"
- **You see empty** → API succeeded, but **no workflows registered yet**

## How to Verify

### Step 1: Check for Demo Mode Banner on Detections Page

Login to https://pisama.ai/detections and look for:

**Option A: Demo Mode (API Failed)**
```
┌─────────────────────────────────────────────────────┐
│ ⚠️ Demo Mode                                        │
│ Unable to connect to API. Showing demo data for     │
│ illustration purposes. Please check your connection │
│ or contact support if this persists.                │
└─────────────────────────────────────────────────────┘
```
→ This means API authentication is failing

**Option B: No Banner (API Working)**
→ This means API is working, and you're seeing real data (could be real or empty)

### Step 2: Check Browser Console

1. Open browser DevTools (F12)
2. Go to **Console** tab
3. Reload the detections page
4. Look for errors like:
   - `API Error: 401` → Authentication problem
   - `API Error: 403` → Permission problem
   - `API Error: 404` → Endpoint not found
   - Network error → Backend down

### Step 3: Check Network Tab

1. Open browser DevTools (F12)
2. Go to **Network** tab
3. Reload each page
4. Filter for `Fetch/XHR`
5. Check API calls:

```
GET /api/v1/detections?perPage=50
Status: 200 OK
Response: []  ← Empty array means no data in database

GET /api/v1/traces?perPage=50
Status: 200 OK
Response: { traces: [], total: 0 }  ← No traces

GET /api/v1/n8n/workflows
Status: 200 OK
Response: []  ← No workflows registered
```

## Most Likely Scenarios

### Scenario 1: Everything Empty (New Installation)
- **Detections**: Demo data (fallback)
- **Traces**: Empty (no data yet)
- **n8n**: Empty (no workflows registered)

**Fix**: You need to:
1. Register n8n workflows
2. Sync executions from n8n
3. Detections will be generated from traces

### Scenario 2: API Authentication Failed
- **Detections**: Demo data (API 401/403)
- **Traces**: Demo data (API 401/403)
- **n8n**: Error (API 401/403)

**Fix**: Check Clerk authentication
- Verify CLERK_PUBLISHABLE_KEY in frontend
- Verify CLERK_SECRET_KEY in backend
- Check if user is properly logged in

### Scenario 3: Real Data Exists (Unexpected)
- **Detections**: Real data from database
- **Traces**: Empty (orphaned detections?)
- **n8n**: Empty (manual trace ingestion?)

**Fix**: Check database integrity
- Run: `fly ssh console -a mao-api`
- Check: `SELECT COUNT(*) FROM detections, traces, n8n_workflows`

## Next Steps

### If you see Demo Mode banner:
```bash
# Check backend is running
curl https://mao-api.fly.dev/health

# Should return: {"status":"healthy"}
```

If health check fails → Backend is down
If health check works → Authentication issue

### If you don't see Demo Mode banner:
Your API is working! The pages are empty because:
1. No n8n workflows registered yet
2. No traces ingested yet
3. No detections generated yet

**To populate with real data:**
1. Go to https://pisama.ai/n8n
2. Click "Register Workflow"
3. Enter your n8n workflow ID
4. Click "Sync from n8n"
5. Wait for executions to sync
6. Traces will appear
7. Detections will be generated from traces

## Quick Test Command

Run this to test API connectivity:

```bash
# Test backend health
curl https://mao-api.fly.dev/health

# Test if API is accessible (will return 401 without auth - that's expected)
curl -i https://mao-api.fly.dev/api/v1/detections

# If you get 200/401/403 → Backend is working
# If you get connection error → Backend is down
```

## Summary Table

| Page | Shows Data | API Call | Database | Explanation |
|------|-----------|----------|----------|-------------|
| Detections | ✅ Yes | ? | ? | Either demo fallback OR real data |
| Traces | ❌ Empty | ✅ Works | Empty | No traces ingested yet |
| n8n | ❌ Empty | ✅ Works | Empty | No workflows registered yet |

## What You Should Do Now

**Please check and report:**
1. ❓ Do you see a yellow "Demo Mode" banner on the detections page?
2. ❓ What's in the browser console when you load detections page?
3. ❓ What's the HTTP status code for `/api/v1/detections` in Network tab?

This will tell us if it's an API issue or just an empty database.
