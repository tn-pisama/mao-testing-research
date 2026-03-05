import { test, expect } from '@playwright/test'

test.describe('Settings - Local Mode', () => {
  test('settings page loads', async ({ page }) => {
    await page.goto('/settings')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
    await expect(page.locator('h1').first()).toContainText(/Settings|Config/i)
    console.log('✅ Settings page loaded')
  })

  test('local mode tab or section exists', async ({ page }) => {
    await page.goto('/settings')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)

    // Look for local mode tab button or section
    const localTab = page.locator('button, a, [role="tab"]').filter({ hasText: /local|lite/i }).first()
    const localSection = page.getByText(/local mode|lite mode|standalone/i).first()

    const tabVisible = await localTab.isVisible().catch(() => false)
    const sectionVisible = await localSection.isVisible().catch(() => false)

    // Either a tab or a section should exist
    expect(tabVisible || sectionVisible).toBe(true)
    console.log(`✅ Local mode: tab=${tabVisible}, section=${sectionVisible}`)
  })
})
