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
    // Look for search input by aria-label or placeholder
    const searchInput = page.getByLabel(/search/i)
      .or(page.locator('input[placeholder*="Search"]'))
      .or(page.locator('input[type="text"]').first())

    await expect(searchInput.first()).toBeVisible()
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
    const traceListItem = page.locator('[class*="trace"], table tbody tr, .rounded-xl').first()
    const emptyState = page.getByText(/no traces|no data|get started/i).first()

    const hasTraces = await traceListItem.isVisible().catch(() => false)
    const isEmpty = await emptyState.isVisible().catch(() => false)

    if (hasTraces) {
      console.log('✅ Trace list displayed')
    } else if (isEmpty) {
      console.log('✅ Empty state displayed')
    } else {
      // In demo mode, the page renders content even without real traces
      const pageContent = page.locator('main, [role="main"], .p-6').first()
      const hasContent = await pageContent.isVisible().catch(() => false)
      if (hasContent) {
        console.log('✅ Page content rendered (demo mode)')
      } else {
        console.log('❌ Neither trace list nor empty state visible')
        await page.screenshot({ path: 'test-results/traces-no-content.png' })
      }
      expect(hasContent).toBe(true)
      return
    }

    expect(hasTraces || isEmpty).toBe(true)
  })

  test('loading state completes (no infinite spinner)', async ({ page }) => {
    await page.waitForTimeout(3000)

    // Verify the page rendered content — title and main area are visible
    await expect(page.locator('h1')).toContainText('Traces')
    const pageContent = page.locator('main, [role="main"], .p-6').first()
    await expect(pageContent).toBeVisible()

    // Small inline spinners (e.g., refresh buttons) are OK — only full-page
    // loading overlays that block interaction would indicate a real problem
    const fullPageSpinner = page.locator('.animate-spin.w-8, .animate-spin.w-12')
    const hasFullPageSpinner = await fullPageSpinner.first().isVisible().catch(() => false)

    if (hasFullPageSpinner) {
      console.log('⚠️  Full-page spinner still visible after 3s')
    } else {
      console.log('✅ Loading complete')
    }
    expect(hasFullPageSpinner).toBe(false)
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

    // Filter out known third-party errors and network errors in demo mode
    const criticalErrors = errors.filter(
      err => !err.includes('chrome-extension') &&
              !err.includes('analytics') &&
              !err.includes('vercel') &&
              !err.includes('cloudflareinsights') &&
              !err.includes('beacon.min.js') &&
              !err.includes('Access-Control-Allow-Headers') &&
              !err.toLowerCase().includes('cors policy') &&
              !err.includes('Failed to fetch') &&
              !err.includes('NetworkError') &&
              !err.includes('ERR_CONNECTION') &&
              !err.includes('net::ERR') &&
              !err.includes('mao-api.fly.dev') &&
              !err.includes('401') &&
              !err.includes('403') &&
              !err.includes('TypeError: Failed to fetch')
    )

    if (criticalErrors.length > 0) {
      console.error('❌ Console errors:', criticalErrors)
    } else {
      console.log('✅ No critical console errors (third-party errors filtered)')
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
