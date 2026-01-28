import { test, expect } from '@playwright/test'

test.describe('Traces Page', () => {
  test('traces page shows Live badge with real data', async ({ page }) => {
    await page.goto('/traces')
    await page.waitForLoadState('networkidle')

    // Check for page title
    await expect(page.locator('h1')).toContainText('Traces')

    // Wait for data to load
    await page.waitForTimeout(3000)

    // Check for Live badge (not Demo Mode)
    const liveBadge = page.locator('span', { hasText: 'Live' })
    await expect(liveBadge).toBeVisible({ timeout: 10000 })

    console.log('✅ Traces page showing Live mode')
  })

  test('traces page loads trace list or empty state', async ({ page }) => {
    await page.goto('/traces')
    await page.waitForLoadState('networkidle')

    // Should show either trace list or empty state, not loading forever
    const loadingIndicator = page.locator('.animate-pulse')
    await expect(loadingIndicator).not.toBeVisible({ timeout: 10000 })

    console.log('✅ Traces page finished loading')
  })

  test('traces page makes API request to backend', async ({ page }) => {
    let apiRequestMade = false

    page.on('request', request => {
      if (request.url().includes('/api/v1/tenants/') && request.url().includes('/traces')) {
        apiRequestMade = true
        console.log(`📡 API request: ${request.url()}`)
      }
    })

    await page.goto('/traces')
    await page.waitForLoadState('networkidle')

    expect(apiRequestMade).toBe(true)
    console.log('✅ Traces API request verified')
  })
})
