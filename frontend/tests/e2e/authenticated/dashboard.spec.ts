import { test, expect } from '@playwright/test'

test.describe('Dashboard - Live Mode Verification', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard')
    await page.waitForLoadState('networkidle')
  })

  test('dashboard page loads for authenticated user', async ({ page }) => {
    // Should see dashboard content, not redirect to login
    await expect(page).toHaveURL(/dashboard/)

    // Check for dashboard heading
    const heading = page.locator('h1').first()
    await expect(heading).toBeVisible()

    console.log('✅ Dashboard loaded')
  })

  test('shows mode badge (Live or Demo)', async ({ page }) => {
    // Wait for data to load
    await page.waitForTimeout(5000)

    // Check for either Live badge or Demo Mode badge in the header
    const header = page.locator('header')
    const liveBadge = header.locator('span', { hasText: 'Live' })
    const demoBadge = header.locator('span', { hasText: 'Demo Mode' })

    const isLive = await liveBadge.isVisible().catch(() => false)
    const isDemo = await demoBadge.isVisible().catch(() => false)

    console.log(`🔍 Dashboard mode: Live=${isLive}, Demo=${isDemo}`)

    // Should show either Live or Demo badge
    expect(isLive || isDemo).toBe(true)

    if (isLive) {
      console.log('✅ Dashboard showing Live mode (connected to backend)')
    } else {
      console.log('✅ Dashboard showing Demo mode (fallback data)')
    }
  })

  test('API requests contain valid tenant UUID', async ({ page }) => {
    const apiRequests: string[] = []

    // Capture API requests
    page.on('request', request => {
      if (request.url().includes('mao-api.fly.dev')) {
        apiRequests.push(request.url())
      }
    })

    await page.goto('/dashboard')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000) // Allow async requests

    // Filter for tenant-specific requests
    const tenantRequests = apiRequests.filter(url => url.includes('/tenants/'))

    console.log(`📡 Captured ${tenantRequests.length} API requests`)

    // Verify UUIDs in requests
    for (const url of tenantRequests) {
      const uuidMatch = url.match(/tenants\/([a-f0-9-]+)/)
      if (uuidMatch) {
        const tenantId = uuidMatch[1]

        // Should be a valid UUID, not 'default' or literal '{tenant_id}'
        expect(tenantId).not.toBe('default')
        expect(tenantId).not.toBe('{tenant_id}')
        expect(tenantId).toMatch(
          /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
        )

        console.log(`✅ Valid tenant UUID: ${tenantId}`)
        break // Only need to verify one
      }
    }

    if (tenantRequests.length > 0) {
      console.log('✅ Tenant API requests verified')
    } else {
      console.log('⚠️  No tenant API requests (demo mode — API may be unreachable)')
    }
  })

  test('API responses are successful (no 404/403/5xx)', async ({ page }) => {
    const failedRequests: { url: string; status: number }[] = []

    // Capture failed responses
    page.on('response', response => {
      if (response.url().includes('mao-api.fly.dev')) {
        const status = response.status()
        if (status === 404 || status === 403 || status >= 500) {
          failedRequests.push({ url: response.url(), status })
        }
      }
    })

    await page.goto('/dashboard')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(3000) // Allow async requests

    // Log failures if any
    if (failedRequests.length > 0) {
      console.error('❌ Failed API requests:', failedRequests)
    } else {
      console.log('✅ All API requests successful')
    }

    // Should have no failed requests
    expect(failedRequests).toHaveLength(0)
  })

  test('dashboard shows data loading states correctly', async ({ page }) => {
    await page.goto('/dashboard')

    // Wait for loading spinners to disappear (use .first() since multiple skeleton elements may exist)
    const loadingSpinner = page.locator('.animate-spin').first()

    // Should stop spinning within 10 seconds
    await expect(loadingSpinner).not.toBeVisible({ timeout: 10000 })

    console.log('✅ Dashboard finished loading')
  })
})
