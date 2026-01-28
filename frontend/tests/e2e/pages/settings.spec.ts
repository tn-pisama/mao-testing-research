import { test, expect } from '@playwright/test'

test.describe('Settings Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/settings')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('page loads and displays title', async ({ page }) => {
    await expect(page.locator('h1').first()).toContainText(/Settings/i)
    console.log('✅ Settings title visible')
  })

  test('settings tabs or sections exist', async ({ page }) => {
    const tabs = page.locator('[role="tablist"], button[role="tab"], [class*="tab"]')
    const count = await tabs.count()

    console.log(`⚙️  Settings tabs/sections: ${count}`)
    expect(count).toBeGreaterThan(0)
  })

  test('settings content is displayed', async ({ page }) => {
    // Look for common settings UI elements
    const inputs = page.locator('input, select, textarea')
    const buttons = page.locator('button')

    const inputCount = await inputs.count()
    const buttonCount = await buttons.count()

    console.log(`✅ Settings UI: ${inputCount} inputs, ${buttonCount} buttons`)
    expect(inputCount + buttonCount).toBeGreaterThan(0)
  })

  test('page is not blank', async ({ page }) => {
    const bodyText = await page.locator('main').first().textContent()
    expect(bodyText).toBeTruthy()
    expect(bodyText!.trim().length).toBeGreaterThan(50)
    console.log('✅ Settings page has content')
  })
})
