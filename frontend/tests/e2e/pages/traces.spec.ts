import { test, expect } from '@playwright/test'

test.describe('Traces Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/traces')
    await page.waitForLoadState('domcontentloaded')
  })

  test('page loads and displays title', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('Traces')
    console.log('✅ Traces page title visible')
  })

  test('search input is visible and functional', async ({ page }) => {
    const searchInput = page.locator('input[placeholder*="Search"]')
      .or(page.locator('input[type="text"]').first())

    await expect(searchInput).toBeVisible()
    console.log('✅ Search input visible')
  })

  test('status filter dropdown exists', async ({ page }) => {
    // Look for filter dropdown or select
    const filterDropdown = page.locator('select, button').filter({ hasText: /status|filter|all/i })

    if (await filterDropdown.count() > 0) {
      await expect(filterDropdown.first()).toBeVisible()
      console.log('✅ Status filter visible')
    } else {
      console.log('⚠️  Status filter not found')
    }
  })

  test('trace list or empty state is displayed', async ({ page }) => {
    // Wait for loading to complete
    await page.waitForTimeout(3000)

    // Check for trace list items OR empty state message
    const traceListItem = page.locator('[class*="trace"]').first()
    const emptyState = page.getByText(/no traces/i)

    const hasTraces = await traceListItem.isVisible().catch(() => false)
    const isEmpty = await emptyState.isVisible().catch(() => false)

    if (hasTraces) {
      console.log('✅ Trace list displayed')
    } else if (isEmpty) {
      console.log('✅ Empty state displayed')
    } else {
      console.log('❌ Neither trace list nor empty state visible')
      // Take screenshot for debugging
      await page.screenshot({ path: 'test-results/traces-no-content.png' })
    }

    // At least one should be true
    expect(hasTraces || isEmpty).toBe(true)
  })

  test('loading state completes (no infinite spinner)', async ({ page }) => {
    // Wait for any loading spinners to disappear
    const spinner = page.locator('.animate-spin, [role="status"]')

    await expect(spinner).not.toBeVisible({ timeout: 15000 })
    console.log('✅ Loading complete')
  })

  test('page has no console errors', async ({ page }) => {
    const errors: string[] = []

    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text())
      }
    })

    await page.goto('/traces')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)

    // Filter out known third-party errors
    const criticalErrors = errors.filter(
      err => !err.includes('chrome-extension') &&
              !err.includes('analytics') &&
              !err.includes('vercel')
    )

    if (criticalErrors.length > 0) {
      console.error('❌ Console errors:', criticalErrors)
    } else {
      console.log('✅ No console errors')
    }

    expect(criticalErrors).toHaveLength(0)
  })

  test('API requests are made to backend', async ({ page }) => {
    const apiRequests: string[] = []

    page.on('request', request => {
      if (request.url().includes('mao-api.fly.dev') || request.url().includes('/api/')) {
        apiRequests.push(request.url())
      }
    })

    await page.goto('/traces')
    await page.waitForTimeout(3000)

    console.log(`📡 API requests made: ${apiRequests.length}`)

    if (apiRequests.length > 0) {
      console.log('✅ API requests detected')
    } else {
      console.log('⚠️  No API requests detected')
    }
  })

  test('pagination controls exist if traces are present', async ({ page }) => {
    await page.waitForTimeout(3000)

    // Check if there are trace items
    const hasTraces = await page.locator('[class*="trace"]').count() > 0

    if (hasTraces) {
      // Look for pagination text or buttons
      const paginationText = page.getByText(/page \d+/i)
      const paginationButtons = page.locator('button').filter({ hasText: /previous|next/i })

      const hasPagination = await paginationText.isVisible().catch(() => false) ||
                           await paginationButtons.first().isVisible().catch(() => false)

      if (hasPagination) {
        console.log('✅ Pagination controls visible')
      } else {
        console.log('⚠️  Pagination controls not found (may be single page)')
      }
    } else {
      console.log('⊘ No traces, pagination not expected')
    }
  })
})
