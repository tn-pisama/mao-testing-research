import { test, expect } from '@playwright/test'

test.describe('Sidebar Navigation', () => {
  test.beforeEach(async ({ page }) => {
    // Start from dashboard
    await page.goto('/dashboard')
    await page.waitForLoadState('domcontentloaded')
  })

  test('Dashboard link navigates correctly', async ({ page }) => {
    await page.click('a[href="/dashboard"]')
    await expect(page).toHaveURL(/dashboard/)
    await expect(page.locator('h1').first()).toContainText(/Dashboard|Workflow Overview/)
    console.log('✅ Dashboard navigation works')
  })

  test('Traces link navigates correctly', async ({ page }) => {
    await page.click('a[href="/traces"]')
    await expect(page).toHaveURL(/traces/)
    await expect(page.locator('h1').first()).toContainText('Traces')
    console.log('✅ Traces navigation works')
  })

  test('Detections link navigates correctly', async ({ page }) => {
    await page.click('a[href="/detections"]')
    await expect(page).toHaveURL(/detections/)
    await expect(page.locator('h1').first()).toContainText(/Detections|Problems Found/)
    console.log('✅ Detections navigation works')
  })

  test('Quality link navigates correctly', async ({ page }) => {
    await page.click('a[href="/quality"]')
    await expect(page).toHaveURL(/quality/)
    await expect(page.locator('h1').first()).toContainText('Quality')
    console.log('✅ Quality navigation works')
  })

  test('Healing link navigates correctly', async ({ page }) => {
    await page.click('a[href="/healing"]')
    await expect(page).toHaveURL(/healing/)
    await expect(page.locator('h1').first()).toContainText(/Self-Healing|Fixes/)
    console.log('✅ Healing navigation works')
  })

  test('Agents link navigates correctly', async ({ page }) => {
    const agentsLink = page.locator('a[href="/agents"]').first()

    // Agents link may not be visible for n8n users
    if (await agentsLink.isVisible()) {
      await agentsLink.click()
      await expect(page).toHaveURL(/agents/)
      await expect(page.locator('h1').first()).toContainText('Agent')
      console.log('✅ Agents navigation works')
    } else {
      console.log('⊘ Agents link not visible (n8n user mode)')
    }
  })

  test('n8n link navigates correctly', async ({ page }) => {
    await page.click('a[href="/n8n"]')
    await expect(page).toHaveURL(/n8n/)
    // n8n page may have different titles
    await expect(page.locator('h1, h2').first()).toBeVisible()
    console.log('✅ n8n navigation works')
  })

  test('Settings link navigates correctly', async ({ page }) => {
    await page.click('a[href="/settings"]')
    await expect(page).toHaveURL(/settings/)
    await expect(page.locator('h1').first()).toContainText('Settings')
    console.log('✅ Settings navigation works')
  })

  test('API Keys link navigates correctly', async ({ page }) => {
    const apiKeysLink = page.locator('a[href="/settings/api-keys"]').first()

    if (await apiKeysLink.isVisible()) {
      await apiKeysLink.click()
      await expect(page).toHaveURL(/api-keys/)
      console.log('✅ API Keys navigation works')
    } else {
      console.log('⊘ API Keys link not visible (n8n user mode)')
    }
  })

  test('sidebar is visible and contains navigation links', async ({ page }) => {
    // Verify sidebar exists
    const sidebar = page.locator('nav').first()
    await expect(sidebar).toBeVisible()

    // Verify key links exist (use .first() to handle duplicate menus)
    await expect(page.locator('a[href="/dashboard"]').first()).toBeVisible()

    // Check that either traces or n8n link is visible
    const hasTraces = await page.locator('a[href="/traces"]').first().isVisible().catch(() => false)
    const hasN8n = await page.locator('a[href="/n8n"]').first().isVisible().catch(() => false)
    expect(hasTraces || hasN8n).toBe(true)

    console.log('✅ Sidebar renders with navigation links')
  })
})
