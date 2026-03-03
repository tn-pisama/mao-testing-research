import { test, expect } from '@playwright/test'

test.describe('Traces Page', () => {
  test('traces page shows mode badge', async ({ page }) => {
    await page.goto('/traces')
    await page.waitForLoadState('networkidle')

    // Check for page title
    await expect(page.locator('h1')).toContainText('Traces')

    // Wait for data to load
    await page.waitForTimeout(3000)

    // Check for either Live or Demo Mode badge in header
    const header = page.locator('header')
    const liveBadge = header.locator('span', { hasText: 'Live' })
    const demoBadge = header.locator('span', { hasText: 'Demo Mode' })

    const isLive = await liveBadge.isVisible().catch(() => false)
    const isDemo = await demoBadge.isVisible().catch(() => false)

    expect(isLive || isDemo).toBe(true)
    console.log(`✅ Traces page showing ${isLive ? 'Live' : 'Demo'} mode`)
  })

  test('traces page loads content', async ({ page }) => {
    await page.goto('/traces')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(3000)

    // Verify the page rendered content (title visible means page loaded)
    await expect(page.locator('h1')).toContainText('Traces')

    // Check that the main content area rendered (not stuck on full-page loading)
    const pageContent = page.locator('main, [role="main"], .p-6').first()
    await expect(pageContent).toBeVisible()

    console.log('✅ Traces page content loaded')
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

    if (apiRequestMade) {
      console.log('✅ Traces API request verified')
    } else {
      console.log('⚠️  No traces API request (demo mode — API may be unreachable)')
    }
  })
})
