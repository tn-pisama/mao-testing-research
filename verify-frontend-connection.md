# Frontend-Backend Connection Verification

## ✅ Infrastructure Status (Confirmed)

### Backend (https://mao-api.fly.dev)
- ✅ Health endpoint responding: `200 OK`
- ✅ Authentication working: `403 Not authenticated` (expected without token)
- ✅ n8n configured in Fly.io secrets:
  - `N8N_HOST` ✓
  - `N8N_API_KEY` ✓
  - `N8N_SYNC_INTERVAL_MINUTES` ✓

### Frontend (https://pisama.ai)
- ✅ Deployed with latest code (commit: 1245b612)
- ✅ Fixed API endpoints: `/api/v1/n8n/*` (no more `/tenants/{tenant_id}` prefix)
- ✅ Real API integration via `useDetections` hook
- ✅ Demo mode indicator implemented

## 🧪 Manual Verification Steps

### Step 1: Login and Check n8n Integration
1. Open https://pisama.ai
2. Login with Clerk authentication
3. Navigate to **n8n** page
4. You should see:
   - List of n8n workflows (or empty state if none registered)
   - "Sync from n8n" button
   - Auto-sync status indicator

### Step 2: Verify Auto-Sync is Running
1. Check the n8n sync status on the n8n page
2. Should show:
   - `auto_sync_enabled: true`
   - `sync_interval_minutes: 5` (or configured value)
   - `n8n_configured: true`

### Step 3: Test Data Flow
1. **Trigger a workflow** in n8n cloud (https://pisama.app.n8n.cloud)
2. Wait 5 minutes for auto-sync OR click "Sync from n8n" manually
3. Navigate to **Traces** page
4. Look for traces with `framework: "n8n"`
5. Verify trace details show:
   - Workflow execution data
   - Steps/nodes from n8n workflow
   - Timestamps matching your execution

### Step 4: Verify Detections Page
1. Navigate to **Detections** page
2. **Check for Demo Mode banner**:
   - ❌ **If you see an amber warning banner** saying "Demo Mode" → API connection failed
   - ✅ **If no banner appears** → API connection working correctly
3. If detections exist, verify they show real data from n8n traces

### Step 5: Check Browser DevTools (Advanced)
1. Open browser DevTools (F12)
2. Go to **Network** tab
3. Reload the Detections page
4. Filter for `fetch/XHR`
5. Look for API calls to:
   - `https://mao-api.fly.dev/api/v1/detections` ✓
   - `https://mao-api.fly.dev/api/v1/n8n/workflows` ✓
   - `https://mao-api.fly.dev/api/v1/n8n/sync` ✓
6. Check response status:
   - `200 OK` = Working correctly ✅
   - `403 Forbidden` = Auth issue ⚠️
   - `404 Not Found` = Endpoint path wrong ❌
   - Network error = Backend down ❌

## 🔍 Expected Behavior

### If Everything Works (✅)
- No "Demo Mode" banner on Detections page
- Real data from n8n workflows appears in Traces
- Detections show actual analysis of n8n traces
- API calls return 200 status codes

### If API Connection Fails (❌)
- Amber "Demo Mode" banner appears
- Message: "Unable to connect to API. Showing demo data..."
- Demo data displayed instead of real data
- Check backend health and authentication

## 📊 Backend Endpoints (Reference)

All endpoints require `Authorization: Bearer <token>` header:

```bash
# Health check (no auth)
GET https://mao-api.fly.dev/health

# n8n endpoints
GET /api/v1/n8n/workflows
POST /api/v1/n8n/sync
GET /api/v1/n8n/sync/status

# Data endpoints
GET /api/v1/traces
GET /api/v1/detections
GET /api/v1/detections/{id}
```

## 🚨 Troubleshooting

### Issue: "Demo Mode" banner appears
**Cause:** Frontend can't reach backend API
**Solutions:**
1. Check if backend is running: `curl https://mao-api.fly.dev/health`
2. Verify authentication token is valid (check browser console)
3. Check CORS configuration in backend

### Issue: No n8n data appears
**Cause:** Auto-sync not running or no executions to sync
**Solutions:**
1. Verify n8n secrets are set: `fly secrets list -a mao-api`
2. Check n8n cloud has recent workflow executions
3. Manually trigger sync from n8n page
4. Check backend logs: `fly logs -a mao-api`

### Issue: 404 on API endpoints
**Cause:** Frontend using old endpoint paths
**Solutions:**
1. Hard refresh browser (Cmd+Shift+R / Ctrl+Shift+F5)
2. Clear browser cache
3. Verify Vercel deployed latest commit: check commit 1245b612

## ✅ Success Criteria

- [ ] Backend health check returns 200
- [ ] Frontend loads without errors
- [ ] No "Demo Mode" banner (when logged in)
- [ ] n8n page shows sync status
- [ ] Traces page shows n8n executions after sync
- [ ] Detections page shows real detection data
- [ ] All API calls return 200 status codes
