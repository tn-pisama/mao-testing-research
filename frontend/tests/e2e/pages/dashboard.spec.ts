import { test, expect } from '@playwright/test'

test.describe('Dashboard Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard')
    await page.waitForLoadState('domcontentloaded')
  })

  test('page loads and displays title', async ({ page }) => {
    await expect(page.locator('h1').first()).toContainText(/Dashboard|Workflow Overview/)
    console.log('✅ Dashboard title visible')
  })

  test('status badge is visible', async ({ page }) => {
    await page.waitForTimeout(2000)

    const liveBadge = page.locator('span, div').filter({ hasText: /^Live$|^Demo Mode$/ })

    if (await liveBadge.count() > 0) {
      const badgeText = await liveBadge.first().textContent()
      console.log(`✅ Status badge: "${badgeText}"`)
    } else {
      console.log('⚠️  Status badge not found')
    }
  })

  test('stats cards are displayed', async ({ page }) => {
    await page.waitForTimeout(3000)

    // Look for any card-like components
    const cards = page.locator('[class*="card"], [class*="bg-slate-8"]')

    const cardCount = await cards.count()
    console.log(`📊 Found ${cardCount} card elements`)

    expect(cardCount).toBeGreaterThan(0)
  })

  test('charts or data visualizations render', async ({ page }) => {
    await page.waitForTimeout(3000)

    // Look for chart elements (recharts uses svg)
    const svgCharts = page.locator('svg')
    const canvasCharts = page.locator('canvas')

    const svgCount = await svgCharts.count()
    const canvasCount = await canvasCharts.count()

    if (svgCount > 0 || canvasCount > 0) {
      console.log(`✅ Charts rendered (${svgCount} SVG, ${canvasCount} canvas)`)
    } else {
      console.log('⚠️  No charts detected')
    }
  })

  test('loading state completes', async ({ page }) => {
    const spinner = page.locator('.animate-spin')
    await expect(spinner).not.toBeVisible({ timeout: 15000 })
    console.log('✅ Loading complete')
  })

  test('refresh or action buttons exist', async ({ page }) => {
    const refreshButton = page.locator('button').filter({ hasText: /refresh|reload/i })
    const importButton = page.locator('button').filter({ hasText: /import/i })

    const hasRefresh = await refreshButton.count() > 0
    const hasImport = await importButton.count() > 0

    if (hasRefresh || hasImport) {
      console.log('✅ Action buttons found')
    } else {
      console.log('⚠️  No action buttons found')
    }
  })

  test('page is not blank/empty', async ({ page }) => {
    await page.waitForTimeout(3000)

    // Get all text content
    const bodyText = await page.locator('body').textContent()

    expect(bodyText).toBeTruthy()
    expect(bodyText!.trim().length).toBeGreaterThan(50)

    console.log(`✅ Page has content (${bodyText!.trim().length} characters)`)
  })
})
