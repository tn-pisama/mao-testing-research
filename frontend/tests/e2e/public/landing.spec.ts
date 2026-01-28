import { test, expect } from '@playwright/test'

test.describe('Landing Page', () => {
  test('landing page loads successfully', async ({ page }) => {
    await page.goto('/')

    // Check for main content
    await expect(page.locator('main')).toBeVisible()

    // Page should not be stuck loading
    await expect(page.getByText('Loading...')).not.toBeVisible({ timeout: 5000 })

    console.log('✅ Landing page loaded')
  })

  test('landing page has correct title', async ({ page }) => {
    await page.goto('/')

    // Verify page title contains expected keywords
    await expect(page).toHaveTitle(/PISAMA|MAO|Testing/)

    console.log('✅ Page title:', await page.title())
  })

  test('sign in button is visible', async ({ page }) => {
    await page.goto('/')

    // Check for sign in button
    const signInButton = page.getByRole('button', { name: /sign in/i })
    await expect(signInButton).toBeVisible()

    console.log('✅ Sign in button found')
  })

  test('page loads without console errors', async ({ page }) => {
    const consoleErrors: string[] = []

    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text())
      }
    })

    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Filter out expected third-party errors
    const criticalErrors = consoleErrors.filter(
      err => !err.includes('third-party') &&
              !err.includes('analytics') &&
              !err.includes('vercel')
    )

    if (criticalErrors.length > 0) {
      console.warn('⚠️  Console errors:', criticalErrors)
    }

    expect(criticalErrors).toHaveLength(0)
  })

  test('landing page is responsive', async ({ page }) => {
    await page.goto('/')

    // Check that main content is visible
    const main = page.locator('main')
    await expect(main).toBeVisible()

    // Ensure page doesn't have horizontal scroll
    const hasHorizontalScroll = await page.evaluate(() => {
      return document.documentElement.scrollWidth > document.documentElement.clientWidth
    })

    expect(hasHorizontalScroll).toBe(false)

    console.log('✅ Page is responsive (no horizontal scroll)')
  })
})
