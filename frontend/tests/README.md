# E2E Test Suite for Frontend-Backend Connection

Automated Playwright tests to verify the PISAMA platform's frontend-backend connectivity.

## Quick Start

### Run Tests Without Authentication

```bash
cd frontend

# Backend health checks
npm run test:api

# Public pages (landing, etc.)
npm run test:public

# Both API and public tests
npm run test:all
```

### Run Tests With Authentication

**One-time setup** (requires manual Google OAuth login):
```bash
npm run test:setup-auth
# Browser opens → Complete Google login → Session saved
```

**Run authenticated tests** (after setup):
```bash
npm run test:auth
```

---

## Test Structure

```
tests/
├── e2e/
│   ├── api/              # Backend API tests (no browser)
│   │   ├── health.spec.ts       # Health endpoint
│   │   └── endpoints.spec.ts    # Endpoint validation
│   ├── public/           # Public pages (no auth)
│   │   └── landing.spec.ts      # Landing page
│   └── authenticated/    # Protected pages (requires auth)
│       ├── dashboard.spec.ts    # Dashboard with "Live" badge
│       └── traces.spec.ts       # Traces page
├── auth/
│   └── storage-state.json       # Saved auth session (gitignored)
└── auth.setup.ts         # Authentication setup script
```

---

## What's Being Tested

### ✅ API Tests (No Auth Required)

| Test | Verifies |
|------|----------|
| Backend health | `https://mao-api.fly.dev/health` returns 200 |
| Latency check | Health endpoint responds within 3 seconds |
| Protected endpoints | Return 401/403 (not 404) without auth |
| CORS headers | Proper CORS configuration |

### ✅ Public Page Tests (No Auth Required)

| Test | Verifies |
|------|----------|
| Landing page loads | Page renders without errors |
| Title correct | Page title contains expected text |
| Sign in button | Authentication UI is present |
| No console errors | No critical JavaScript errors |
| Responsive | No horizontal scroll |

### ✅ Authenticated Tests (Auth Required)

| Test | Verifies |
|------|----------|
| Dashboard loads | Protected page accessible when logged in |
| **Live badge shown** | "Live" badge visible, NOT "Demo Mode" |
| Valid tenant UUIDs | API requests use real UUIDs (not `{tenant_id}`) |
| API calls succeed | No 404/403/5xx responses |
| Traces page works | Traces load correctly with Live badge |

---

## Configuration

### Environment Variables

Tests use `.env.test` configuration:

```bash
TEST_BASE_URL=https://pisama.ai
TEST_API_URL=https://mao-api.fly.dev
```

### Playwright Config

See `playwright.config.ts` for:
- Production URLs
- Test projects (api, public, authenticated)
- Browser settings
- Retry logic

---

## Authentication Setup

The authenticated tests require a one-time manual login:

### How It Works

1. Run `npm run test:setup-auth`
2. Browser opens to `/sign-in`
3. You have 90 seconds to complete Google OAuth
4. Session saved to `tests/auth/storage-state.json`
5. Future tests reuse this session

### When to Re-run

- Session expires (typically 7-30 days)
- Different user account needed
- Tests start failing with 401/403 errors

---

## Troubleshooting

### Tests Timeout

**Symptom**: All tests timeout after 30 seconds

**Cause**: Backend at `https://mao-api.fly.dev` is sleeping or not responding

**Solution**:
```bash
# Wake up backend manually
curl https://mao-api.fly.dev/health

# Wait 30 seconds for backend to start
# Then re-run tests
```

### "Demo Mode" Badge Shows

**Symptom**: Dashboard shows "Demo Mode" instead of "Live"

**Cause**: Frontend cannot connect to backend API

**Check**:
1. Backend health: `curl https://mao-api.fly.dev/health`
2. Browser console for CORS errors
3. Vercel environment variable: `NEXT_PUBLIC_API_URL`

### Storage State Not Found

**Symptom**: `Error: storage-state.json file not found`

**Solution**: Run auth setup first
```bash
npm run test:setup-auth
```

---

## CI/CD Integration

Tests are designed to run in GitHub Actions:

```yaml
- name: Run E2E tests
  run: |
    cd frontend
    npm run test:api     # Backend health
    npm run test:public  # Landing page
    npm run test:auth    # Dashboard (requires auth setup)
```

---

## Verification Checklist

After running tests, verify:

- [ ] ✅ Backend health returns 200
- [ ] ✅ Landing page loads without errors
- [ ] ✅ Protected endpoints return 401/403 (not 404)
- [ ] ✅ Dashboard shows "Live" badge (not "Demo Mode")
- [ ] ✅ API requests use real tenant UUIDs
- [ ] ✅ No failed API requests (404/403/5xx)

---

## Scripts Reference

| Command | Description |
|---------|-------------|
| `npm run test` | Run all Playwright tests |
| `npm run test:api` | Backend API health checks |
| `npm run test:public` | Public pages (no auth) |
| `npm run test:auth` | Authenticated pages |
| `npm run test:all` | API + Public tests |
| `npm run test:setup-auth` | One-time auth setup |
| `npm run test:report` | Open test results HTML report |

---

## Known Issues

### Backend Connectivity

The Fly.io backend at `https://mao-api.fly.dev` sometimes:
- Takes 20-30 seconds to wake from sleep
- Fails to bind to 0.0.0.0:8000 correctly
- Requires manual wake-up before tests run

**Workaround**: Manually curl the health endpoint before running tests.

---

## Test Development

### Adding New Tests

1. Create test file in appropriate directory (`api/`, `public/`, or `authenticated/`)
2. Import from `@playwright/test`
3. Follow existing patterns
4. Run with `npx playwright test your-test.spec.ts`

### Example Test

```typescript
import { test, expect } from '@playwright/test'

test('my new test', async ({ page }) => {
  await page.goto('/my-page')
  await expect(page.locator('h1')).toBeVisible()
})
```

---

For more information, see the [Playwright documentation](https://playwright.dev).
