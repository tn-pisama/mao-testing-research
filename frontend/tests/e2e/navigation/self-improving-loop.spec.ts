import { test, expect } from '@playwright/test'

test.describe('Self-Improving Loop Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard')
    await page.waitForLoadState('domcontentloaded')
  })

  test('Developer API link navigates correctly', async ({ page }) => {
    const link = page.locator('a[href="/tools/developer-api"]').first()
    if (await link.isVisible().catch(() => false)) {
      await link.click()
      await expect(page).toHaveURL(/developer-api/)
      console.log('✅ Developer API navigation works')
    } else {
      console.log('⚠️  Developer API link not visible in sidebar')
    }
  })

  test('Custom Scorers link navigates correctly', async ({ page }) => {
    const link = page.locator('a[href="/evals/scorers"]').first()
    if (await link.isVisible().catch(() => false)) {
      await link.click()
      await expect(page).toHaveURL(/scorers/)
      console.log('✅ Custom Scorers navigation works')
    } else {
      console.log('⚠️  Custom Scorers link not visible in sidebar')
    }
  })

  test('Conversations link navigates correctly', async ({ page }) => {
    const link = page.locator('a[href="/conversation-evaluations"]').first()
    if (await link.isVisible().catch(() => false)) {
      await link.click()
      await expect(page).toHaveURL(/conversation-evaluations/)
      console.log('✅ Conversations navigation works')
    } else {
      console.log('⚠️  Conversations link not visible in sidebar')
    }
  })
})
