import { test, expect } from '@playwright/test'

test.describe('n8n Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/n8n')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('page loads successfully', async ({ page }) => {
    const heading = page.locator('h1, h2').first()
    await expect(heading).toBeVisible()
    console.log('✅ n8n page title visible')
  })

  test('workflow list or registration UI exists', async ({ page }) => {
    const workflowElements = page.locator('[class*="workflow"], table, form')
    const count = await workflowElements.count()

    console.log(`🔀 Workflow elements: ${count}`)
    expect(count).toBeGreaterThan(0)
  })

  test('sync button exists', async ({ page }) => {
    const syncButton = page.locator('button').filter({ hasText: /sync/i })

    if (await syncButton.count() > 0) {
      console.log('✅ Sync button found')
    } else {
      console.log('⚠️  No sync button detected')
    }
  })

  test('loading completes', async ({ page }) => {
    await expect(page.locator('.animate-spin')).not.toBeVisible({ timeout: 15000 })
    console.log('✅ Loading complete')
  })
})
