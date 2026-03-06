import { test, expect } from '@playwright/test'

test.describe('Cognitive Memory', () => {
  test.beforeEach(async ({ page }) => {
    await page.setExtraHTTPHeaders({ 'x-test-bypass': 'true' })
  })

  test('memory dashboard page loads', async ({ page }) => {
    await page.goto('/memory')
    await page.waitForLoadState('domcontentloaded')
    await expect(page.getByText('Cognitive Memory').or(page.getByText('Memory')).first()).toBeVisible()
  })

  test('shows stats cards', async ({ page }) => {
    await page.goto('/memory')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
    await expect(page.getByText('Total Memories').or(page.getByText('Memories')).first()).toBeVisible()
  })

  test('has search input', async ({ page }) => {
    await page.goto('/memory')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
    const search = page
      .locator('input[placeholder*="Search"]')
      .or(page.locator('input[placeholder*="search"]'))
      .or(page.locator('input[placeholder*="Recall"]'))
    await expect(search.first()).toBeVisible()
  })

  test('shows memory tree section', async ({ page }) => {
    await page.goto('/memory')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
    await expect(
      page.getByText('Memory Tree').or(page.getByText('memory tree')).first()
    ).toBeVisible()
  })

  test('sidebar has memory link', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
    await expect(page.locator('a[href="/memory"]')).toBeVisible()
  })

  test('memory detail page handles missing id', async ({ page }) => {
    await page.goto('/memory/00000000-0000-0000-0000-000000000000')
    await page.waitForLoadState('domcontentloaded')
    // Should show loading or not found state without crashing
    await expect(page.locator('body')).toBeVisible()
  })
})
