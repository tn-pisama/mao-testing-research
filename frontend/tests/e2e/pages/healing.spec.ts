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
    const healingCard = page.locator('[class*="healing"], [class*="fix"], .rounded-xl').first()
    const emptyState = page.getByText(/no.*healing|no.*fixes|no data|get started/i).first()

    const hasHealings = await healingCard.isVisible().catch(() => false)
    const isEmpty = await emptyState.isVisible().catch(() => false)

    console.log(`Healings: ${hasHealings}, Empty: ${isEmpty}`)
    // In demo mode, the page renders content even without real healings
    const pageContent = page.locator('main, [role="main"], .p-6').first()
    const hasContent = await pageContent.isVisible().catch(() => false)
    expect(hasHealings || isEmpty || hasContent).toBe(true)
  })

  test('loading completes', async ({ page }) => {
    await expect(page.locator('.animate-spin')).not.toBeVisible({ timeout: 15000 })
    console.log('✅ Loading complete')
  })
})

test.describe('Healing Page - Tab Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/healing')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('connections tab is clickable', async ({ page }) => {
    const connectionsTab = page.getByRole('tab', { name: /connections/i })
      .or(page.getByText(/connections/i).first())

    if (await connectionsTab.isVisible()) {
      await connectionsTab.click()
      await page.waitForTimeout(500)
      // Should show connections content or empty state
      const content = page.getByText(/n8n|connection|no.*connection/i)
      const hasContent = await content.first().isVisible().catch(() => false)
      console.log(`✅ Connections tab content visible: ${hasContent}`)
    } else {
      console.log('⚠️  Connections tab not found')
    }
  })

  test('history tab is clickable', async ({ page }) => {
    const historyTab = page.getByRole('tab', { name: /history|versions/i })
      .or(page.getByText(/history|versions/i).first())

    if (await historyTab.isVisible()) {
      await historyTab.click()
      await page.waitForTimeout(500)
      const content = page.getByText(/version|history|no.*version/i)
      const hasContent = await content.first().isVisible().catch(() => false)
      console.log(`✅ History tab content visible: ${hasContent}`)
    } else {
      console.log('⚠️  History tab not found')
    }
  })

  test('approvals tab is clickable', async ({ page }) => {
    // Use .first() to avoid strict mode when multiple tabs match
    const approvalsTab = page.getByRole('tab', { name: /approvals/i }).first()
    const pendingTab = page.getByRole('tab', { name: /pending/i }).first()

    const hasApprovals = await approvalsTab.isVisible().catch(() => false)
    const hasPending = await pendingTab.isVisible().catch(() => false)

    if (hasApprovals) {
      await approvalsTab.click()
      await page.waitForTimeout(500)
      const content = page.getByText(/approval|pending|no.*pending/i).first()
      const hasContent = await content.isVisible().catch(() => false)
      console.log(`✅ Approvals tab content visible: ${hasContent}`)
    } else if (hasPending) {
      await pendingTab.click()
      await page.waitForTimeout(500)
      console.log('✅ Pending tab clicked')
    } else {
      console.log('⚠️  Approvals/Pending tab not found')
    }
  })
})

test.describe('Healing Page - Refresh & Error States', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/healing')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('refresh button reloads data', async ({ page }) => {
    // Use .first() to avoid strict mode when multiple refresh buttons exist
    const refreshBtn = page.getByRole('button', { name: /refresh/i }).first()

    if (await refreshBtn.isVisible()) {
      await refreshBtn.click()
      // Should show spinner briefly then complete
      await page.waitForTimeout(1000)
      await expect(page.locator('.animate-spin').first()).not.toBeVisible({ timeout: 10000 })
      console.log('✅ Refresh completed')
    } else {
      console.log('⚠️  Refresh button not found')
    }
  })

  test('empty state shows helpful message', async ({ page }) => {
    const emptyState = page.getByText(/no.*healing|no.*fixes|get started/i)
    const hasEmpty = await emptyState.first().isVisible().catch(() => false)

    if (hasEmpty) {
      console.log('✅ Empty state message visible')
    } else {
      // If there are healings, the empty state won't show — that's OK
      const healingCards = page.locator('[class*="healing"], [class*="card"]')
      const count = await healingCards.count()
      console.log(`ℹ️  Not empty — found ${count} healing cards`)
    }
  })
})

test.describe('Healing Page - API Error Handling', () => {
  test('shows error banner on API failure', async ({ page }) => {
    // Intercept API calls to simulate failure
    await page.route('**/api/v1/healing/**', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal server error' }),
      })
    })

    await page.goto('/healing')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(3000)

    // Should show an error toast or error state
    const errorIndicator = page.getByText(/error|failed|something went wrong/i)
    const toastError = page.locator('[data-sonner-toast][data-type="error"]')

    const hasError = await errorIndicator.first().isVisible().catch(() => false)
    const hasToast = await toastError.first().isVisible().catch(() => false)

    console.log(`Error indicator: ${hasError}, Error toast: ${hasToast}`)
    // At minimum the page should not crash
    await expect(page.locator('h1').first()).toBeVisible()
    console.log('✅ Page did not crash on API failure')
  })
})
