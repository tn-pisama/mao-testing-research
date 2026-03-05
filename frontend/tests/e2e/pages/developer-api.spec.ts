import { test, expect } from '@playwright/test'

test.describe('Developer API Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/tools/developer-api')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('page loads with title', async ({ page }) => {
    await expect(page.locator('h1').first()).toContainText(/Developer|API|MCP/i)
    console.log('✅ Developer API title visible')
  })

  test('shows MCP setup instructions', async ({ page }) => {
    const codeBlock = page.locator('pre, code').first()
    await expect(codeBlock).toBeVisible()
    console.log('✅ MCP setup instructions visible')
  })

  test('shows available tools list', async ({ page }) => {
    await expect(page.getByText(/pisama_query_traces|query_traces/i).first()).toBeVisible()
    console.log('✅ Available tools list visible')
  })

  test('has link to API keys', async ({ page }) => {
    const link = page.locator('a[href*="api-keys"], a[href*="settings"]').first()
    await expect(link).toBeVisible()
    console.log('✅ API keys link visible')
  })
})
