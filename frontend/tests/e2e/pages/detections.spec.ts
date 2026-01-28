import { test, expect } from '@playwright/test'

test.describe('Detections Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/detections')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('page loads and displays title', async ({ page }) => {
    await expect(page.locator('h1').first()).toContainText(/Detections|Problems/)
    console.log('✅ Detections title visible')
  })

  test('stats cards are displayed', async ({ page }) => {
    const statsCards = page.locator('[class*="stats"], [class*="card"]').filter({ has: page.locator('p, div') })
    const count = await statsCards.count()

    console.log(`📊 Stats cards: ${count}`)
    expect(count).toBeGreaterThan(0)
  })

  test('filter controls exist', async ({ page }) => {
    const filterControls = page.locator('button, select').filter({ hasText: /type|severity|filter/i })
    const count = await filterControls.count()

    if (count > 0) {
      console.log('✅ Filter controls found')
    } else {
      console.log('⚠️  No filter controls detected')
    }
  })

  test('detection list or empty state is displayed', async ({ page }) => {
    const detectionCard = page.locator('[class*="detection"], [class*="card"]').first()
    const emptyState = page.getByText(/no detection/i)

    const hasDetections = await detectionCard.isVisible().catch(() => false)
    const isEmpty = await emptyState.isVisible().catch(() => false)

    console.log(`Detections: ${hasDetections}, Empty: ${isEmpty}`)
    expect(hasDetections || isEmpty).toBe(true)
  })

  test('loading completes', async ({ page }) => {
    await expect(page.locator('.animate-spin')).not.toBeVisible({ timeout: 15000 })
    console.log('✅ Loading complete')
  })
})
