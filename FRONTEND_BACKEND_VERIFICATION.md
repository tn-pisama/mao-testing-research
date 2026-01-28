# Frontend-Backend Connection Verification Report

**Date**: 2026-01-28
**Status**: Backend operational, ready for visual testing

## Pre-flight Checks

### ✅ Backend Health
```bash
$ curl https://mao-api.fly.dev/health
{"status":"healthy"}
```

### ✅ Fly.io Status
- App: mao-api
- Machines: 2 instances running in `sjc` region
- Status: Started and responding
- Note: App was sleeping, woke up on first request

### ✅ Frontend Accessibility
```bash
$ curl -I https://pisama.ai
HTTP/2 200
```

---

## Visual Verification Checklist

Follow these steps in your browser to verify the frontend-backend connection:

### Step 1: Open Dashboard
1. Navigate to: https://pisama.ai/dashboard
2. Log in with your Clerk/Google account
3. **Check for badge near "Dashboard" title:**
   - ✅ Green badge with "Live" = Connected to backend
   - ❌ Amber badge with "Demo Mode" = Using fallback data

### Step 2: Verify Traces Page
1. Navigate to: https://pisama.ai/traces
2. **Check for badge near "Traces" title:**
   - ✅ Green "Live" = Real data
   - ❌ Amber "Demo Mode" = Fallback
3. **Inspect trace IDs:**
   - Real data: UUIDs like `550e8400-e29b-41d4-a716-446655440000`
   - Demo data: Short IDs like `abc123xyz`

### Step 3: Verify Detections Page
1. Navigate to: https://pisama.ai/detections
2. **Check for banner at top:**
   - ✅ No banner = Connected
   - ❌ Yellow banner saying "Demo Mode - Unable to connect to API" = Failed

### Step 4: Verify Quality Page
1. Navigate to: https://pisama.ai/quality
2. **Expected:**
   - Empty state with "No quality assessments found" = Connected but no data
   - OR list of assessments = Connected with data
   - ❌ Error message = Connection failed

### Step 5: Verify Healing Page
1. Navigate to: https://pisama.ai/healing
2. **Expected:**
   - Tabs for "Healings", "Connections", "Version History" visible
   - Empty state or data displayed = Connected
   - ❌ Error banner = Connection failed

### Step 6: Verify n8n Integration
1. Navigate to: https://pisama.ai/n8n
2. **Expected:**
   - "Register Workflow" button visible
   - "Sync from n8n" button visible
   - Workflow list (empty or populated) = Connected
   - ❌ Error message = Connection failed

---

## Browser DevTools Verification

1. Open any page (e.g., /dashboard)
2. Press F12 to open DevTools
3. Go to **Network** tab
4. Filter by "Fetch/XHR"
5. Reload the page
6. **Look for these requests:**

| Request Path | Expected Status | What It Means |
|--------------|-----------------|---------------|
| `/api/v1/tenants/{uuid}/analytics/loops` | 200 OK | Loop analytics working |
| `/api/v1/tenants/{uuid}/analytics/cost` | 200 OK | Cost analytics working |
| `/api/v1/tenants/{uuid}/detections` | 200 OK | Detections API working |
| `/api/v1/tenants/{uuid}/traces` | 200 OK | Traces API working |

**Critical Check**: Verify the {uuid} in URLs is a real UUID (like `550e8400-e29b-...`), NOT the literal string `{tenant_id}`.

### Example of Correct Request:
```
GET https://mao-api.fly.dev/api/v1/tenants/550e8400-e29b-41d4-a716-446655440000/traces
Status: 200 OK
```

### Example of Broken Request:
```
GET https://mao-api.fly.dev/api/v1/tenants/{tenant_id}/traces
Status: 404 Not Found
```

---

## Data Authenticity Indicators

| Demo Data | Real Data |
|-----------|-----------|
| IDs: `abc123`, `xyz789` | UUIDs: `550e8400-e29b-...` |
| Frameworks: Random (`langgraph`, `autogen`, `crewai`) | Consistent (likely `n8n`) |
| Session IDs: `session-abc123` | Backend patterns |
| Timestamps: Random last 48h | Real execution times |

---

## Troubleshooting

### Issue: "Demo Mode" badge on all pages
**Diagnosis**: Backend not reachable from frontend
**Check**:
```bash
curl https://mao-api.fly.dev/health
```
**Solutions**:
- Backend may be sleeping (wait 30s for first request)
- Check CORS configuration
- Verify Clerk authentication

### Issue: 403 Forbidden errors in Network tab
**Diagnosis**: Authentication issue
**Solutions**:
- Log out and log back in
- Check Clerk credentials in Vercel environment variables
- Verify API token is being sent in Authorization header

### Issue: URLs contain `{tenant_id}` literal
**Diagnosis**: Tenant ID not resolved from auth session
**Solutions**:
- Check `useTenant` hook in frontend/src/hooks/useTenant.ts
- Verify Clerk session contains organization ID
- Check browser console for errors

### Issue: Empty pages without errors
**Diagnosis**: No data in database
**Solutions**:
- Go to /n8n page and click "Sync from n8n"
- Register an n8n workflow
- Import sample data

---

## Success Criteria

- [x] Backend health returns 200 ✅
- [x] Frontend loads without errors ✅
- [ ] Dashboard shows "Live" badge (not "Demo Mode")
- [ ] Traces page shows "Live" badge
- [ ] Detections page has no demo banner
- [ ] Network requests return 200 status
- [ ] Request URLs contain real tenant UUID
- [ ] Quality page loads without error
- [ ] Healing page loads without error

---

## Next Steps

After visual verification:
1. If all pages show "Live" badges → **Frontend-Backend connection is working correctly**
2. If pages show "Demo Mode" → Investigate authentication and CORS
3. If specific pages fail → Check those specific API endpoints
4. Test end-to-end flow: Register n8n workflow → Sync → View traces → Check detections

---

## Backend Configuration Reference

**Backend URL**: https://mao-api.fly.dev
**Frontend URL**: https://pisama.ai
**API Base Path**: `/api/v1`
**Health Endpoint**: `/health`

**Environment Variables** (set in Vercel for frontend):
- `NEXT_PUBLIC_API_URL=https://mao-api.fly.dev/api/v1`
- Clerk credentials for authentication
