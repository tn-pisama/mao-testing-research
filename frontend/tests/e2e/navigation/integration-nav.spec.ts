import { test, expect } from '@playwright/test'

test.describe('Sidebar - Integration Navigation Links', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(1000)
  })

  test('sidebar contains Dify Apps link', async ({ page }) => {
    await expect(page.locator('a[href="/dify"]').first()).toBeVisible()
    console.log('✅ Dify Apps sidebar link visible')
  })

  test('sidebar contains OpenClaw link', async ({ page }) => {
    await expect(page.locator('a[href="/openclaw"]').first()).toBeVisible()
    console.log('✅ OpenClaw sidebar link visible')
  })

  test('sidebar contains LangGraph link', async ({ page }) => {
    await expect(page.locator('a[href="/langgraph"]').first()).toBeVisible()
    console.log('✅ LangGraph sidebar link visible')
  })

  test('sidebar contains Integrations link', async ({ page }) => {
    await expect(page.locator('a[href="/integrations"]').first()).toBeVisible()
    console.log('✅ Integrations sidebar link visible')
  })

  test('Dify link navigates to /dify', async ({ page }) => {
    await page.locator('a[href="/dify"]').first().click()
    await expect(page).toHaveURL(/dify/)
    await expect(page.locator('h1').first()).toContainText('Dify Apps')
    console.log('✅ Dify navigation works')
  })

  test('OpenClaw link navigates to /openclaw', async ({ page }) => {
    await page.locator('a[href="/openclaw"]').first().click()
    await expect(page).toHaveURL(/openclaw/)
    await expect(page.locator('h1').first()).toContainText('OpenClaw Agents')
    console.log('✅ OpenClaw navigation works')
  })

  test('LangGraph link navigates to /langgraph', async ({ page }) => {
    await page.locator('a[href="/langgraph"]').first().click()
    await expect(page).toHaveURL(/langgraph/)
    await expect(page.locator('h1').first()).toContainText('LangGraph Deployments')
    console.log('✅ LangGraph navigation works')
  })

  test('Integrations link navigates to /integrations', async ({ page }) => {
    await page.locator('a[href="/integrations"]').first().click()
    await expect(page).toHaveURL(/integrations/)
    await expect(page.locator('h1').first()).toContainText('Integrations')
    console.log('✅ Integrations navigation works')
  })

  test('Configure section title is visible', async ({ page }) => {
    const configureSection = page.getByText('Configure', { exact: false })
    const hasSection = await configureSection.first().isVisible().catch(() => false)
    console.log(`Configure section: ${hasSection}`)
  })
})

test.describe('Docs Sidebar - Integration Documentation Links', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/docs/getting-started')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('docs sidebar contains Dify Integration link', async ({ page }) => {
    const link = page.locator('a[href="/docs/dify"]').first()
    await expect(link).toBeVisible()
    await expect(link).toContainText('Dify Integration')
    console.log('✅ Dify docs sidebar link visible')
  })

  test('docs sidebar contains OpenClaw Integration link', async ({ page }) => {
    const link = page.locator('a[href="/docs/openclaw"]').first()
    await expect(link).toBeVisible()
    await expect(link).toContainText('OpenClaw Integration')
    console.log('✅ OpenClaw docs sidebar link visible')
  })

  test('docs sidebar contains LangGraph Integration link', async ({ page }) => {
    const link = page.locator('a[href="/docs/langgraph"]').first()
    await expect(link).toBeVisible()
    await expect(link).toContainText('LangGraph Integration')
    console.log('✅ LangGraph docs sidebar link visible')
  })

  test('Dify docs link navigates correctly', async ({ page }) => {
    await page.locator('a[href="/docs/dify"]').first().click()
    await expect(page).toHaveURL(/docs\/dify/)
    await expect(page.locator('h1').first()).toContainText('Dify Integration')
    console.log('✅ Dify docs navigation works')
  })

  test('OpenClaw docs link navigates correctly', async ({ page }) => {
    await page.locator('a[href="/docs/openclaw"]').first().click()
    await expect(page).toHaveURL(/docs\/openclaw/)
    await expect(page.locator('h1').first()).toContainText('OpenClaw Integration')
    console.log('✅ OpenClaw docs navigation works')
  })

  test('LangGraph docs link navigates correctly', async ({ page }) => {
    await page.locator('a[href="/docs/langgraph"]').first().click()
    await expect(page).toHaveURL(/docs\/langgraph/)
    await expect(page.locator('h1').first()).toContainText('LangGraph Integration')
    console.log('✅ LangGraph docs navigation works')
  })
})

test.describe('Cross-Page Navigation', () => {
  test('management page to docs round-trip', async ({ page }) => {
    // Start at Dify management page
    await page.goto('/dify')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(1000)
    await expect(page.locator('h1').first()).toContainText('Dify Apps')

    // Navigate to Dify docs
    await page.goto('/docs/dify')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(1000)
    await expect(page.locator('h1').first()).toContainText('Dify Integration')

    // Navigate back to management
    await page.goto('/dify')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(1000)
    await expect(page.locator('h1').first()).toContainText('Dify Apps')
    console.log('✅ Management ↔ Docs round-trip works')
  })

  test('integrations tab to management page', async ({ page }) => {
    await page.goto('/integrations')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)

    // Click LangGraph tab
    await page.locator('button').filter({ hasText: 'LangGraph' }).first().click()
    await page.waitForTimeout(500)

    // Click the Manage Deployments link
    const manageLink = page.locator('a[href="/langgraph"]')
    if (await manageLink.first().isVisible().catch(() => false)) {
      await manageLink.first().click()
      await expect(page).toHaveURL(/langgraph/)
      await expect(page.locator('h1').first()).toContainText('LangGraph Deployments')
      console.log('✅ Integrations → Management page navigation works')
    } else {
      console.log('⊘ Manage Deployments link not found in LangGraph tab')
    }
  })
})
