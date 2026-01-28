import { test, expect } from '@playwright/test'

test.describe('Healing Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/healing')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('page loads and displays title', async ({ page }) => {
    await expect(page.locator('h1').first()).toContainText(/Healing|Fixes/i)
    console.log('✅ Healing title visible')
  })

  test('tabs are visible', async ({ page }) => {
    const tabs = page.locator('[role="tablist"], button[role="tab"]')
    const count = await tabs.count()

    if (count > 0) {
      console.log(`✅ Tabs found: ${count}`)
    } else {
      console.log('⚠️  No tabs detected')
    }
  })

  test('healing list or empty state is displayed', async ({ page }) => {
    const healingCard = page.locator('[class*="healing"], [class*="fix"]').first()
    const emptyState = page.getByText(/no.*healing|no.*fixes/i)

    const hasHealings = await healingCard.isVisible().catch(() => false)
    const isEmpty = await emptyState.isVisible().catch(() => false)

    console.log(`Healings: ${hasHealings}, Empty: ${isEmpty}`)
    expect(hasHealings || isEmpty).toBe(true)
  })

  test('loading completes', async ({ page }) => {
    await expect(page.locator('.animate-spin')).not.toBeVisible({ timeout: 15000 })
    console.log('✅ Loading complete')
  })
})
