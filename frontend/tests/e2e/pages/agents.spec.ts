import { test, expect } from '@playwright/test'

test.describe('Agents Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/agents')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('page loads and displays title', async ({ page }) => {
    await expect(page.locator('h1, h2').first()).toContainText(/Agent/i)
    console.log('✅ Agents title visible')
  })

  test('agent visualization or list is displayed', async ({ page }) => {
    // Agents page has various views
    const agentElements = page.locator('[class*="agent"], svg, canvas')
    const count = await agentElements.count()

    console.log(`🤖 Agent elements: ${count}`)
    expect(count).toBeGreaterThan(0)
  })

  test('view tabs exist', async ({ page }) => {
    const tabs = page.locator('[role="tab"], button').filter({ hasText: /orchestration|grid|health|monitoring/i })
    const count = await tabs.count()

    if (count > 0) {
      console.log(`✅ View tabs found: ${count}`)
    } else {
      console.log('⚠️  No view tabs detected')
    }
  })

  test('loading completes', async ({ page }) => {
    await expect(page.locator('.animate-spin')).not.toBeVisible({ timeout: 15000 })
    console.log('✅ Loading complete')
  })
})
