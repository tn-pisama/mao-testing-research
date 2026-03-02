import { test, expect } from '@playwright/test'

test.describe('Dify Page - Core Rendering', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dify')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('page loads and displays title', async ({ page }) => {
    await expect(page.locator('h1').first()).toContainText('Dify Apps')
    console.log('✅ Dify page title visible')
  })

  test('description text is visible', async ({ page }) => {
    await expect(page.getByText('Connect Dify instances for automated trace ingestion')).toBeVisible()
    console.log('✅ Description visible')
  })

  test('loading completes', async ({ page }) => {
    await expect(page.locator('.animate-spin')).not.toBeVisible({ timeout: 15000 })
    console.log('✅ Loading complete')
  })

  test('demo mode badge is shown', async ({ page }) => {
    const demoBadge = page.getByText('Demo Mode')
    const hasDemoBadge = await demoBadge.first().isVisible().catch(() => false)
    console.log(`Demo Mode badge: ${hasDemoBadge}`)
    // In demo mode (no backend) the badge should appear
    expect(hasDemoBadge).toBe(true)
  })

  test('Add Instance button is visible', async ({ page }) => {
    await expect(page.getByRole('button', { name: /Add Instance/i })).toBeVisible()
    console.log('✅ Add Instance button visible')
  })

  test('Register App button exists', async ({ page }) => {
    await expect(page.getByRole('button', { name: /Register App/i })).toBeVisible()
    console.log('✅ Register App button visible')
  })

  test('webhook URL banner shows dify endpoint', async ({ page }) => {
    await expect(page.getByText('Webhook URL').first()).toBeVisible()
    await expect(page.locator('code').filter({ hasText: 'dify/webhook' })).toBeVisible()
    console.log('✅ Webhook URL banner visible')
  })

  test('setup instructions section with 4 steps', async ({ page }) => {
    await expect(page.getByText('Setup Instructions')).toBeVisible()
    const steps = page.locator('ol li, .space-y-3 > li')
    const count = await steps.count()
    console.log(`📋 Setup steps found: ${count}`)
    expect(count).toBeGreaterThanOrEqual(4)
  })
})

test.describe('Dify Page - Instance Form Modal', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dify')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('clicking Add Instance opens modal', async ({ page }) => {
    await expect(page.getByText('Add Dify Instance')).not.toBeVisible()
    await page.getByRole('button', { name: /Add Instance/i }).click()
    await expect(page.getByText('Add Dify Instance')).toBeVisible()
    console.log('✅ Instance modal opens')
  })

  test('instance modal has 3 required fields', async ({ page }) => {
    await page.getByRole('button', { name: /Add Instance/i }).click()
    await expect(page.getByText('Instance Name *')).toBeVisible()
    await expect(page.getByText('Base URL *')).toBeVisible()
    await expect(page.getByText('API Key *')).toBeVisible()
    console.log('✅ All 3 required fields visible')
  })

  test('modal has Register and Cancel buttons', async ({ page }) => {
    await page.getByRole('button', { name: /Add Instance/i }).click()
    // Inside the modal, look for Register and Cancel buttons
    const modalButtons = page.locator('.fixed button, .fixed [role="button"]')
    const registerBtn = page.locator('.fixed').getByRole('button', { name: /^Register$/i })
    const cancelBtn = page.locator('.fixed').getByRole('button', { name: /Cancel/i })
    await expect(registerBtn).toBeVisible()
    await expect(cancelBtn).toBeVisible()
    console.log('✅ Register and Cancel buttons in modal')
  })

  test('Cancel closes the modal', async ({ page }) => {
    await page.getByRole('button', { name: /Add Instance/i }).click()
    await expect(page.getByText('Add Dify Instance')).toBeVisible()
    await page.locator('.fixed').getByRole('button', { name: /Cancel/i }).click()
    await expect(page.getByText('Add Dify Instance')).not.toBeVisible()
    console.log('✅ Modal closed on Cancel')
  })

  test('empty form shows validation error', async ({ page }) => {
    await page.getByRole('button', { name: /Add Instance/i }).click()
    await page.locator('.fixed').getByRole('button', { name: /^Register$/i }).click()
    await expect(page.getByText('Name, Base URL, and API Key are required')).toBeVisible()
    console.log('✅ Validation error shown')
  })
})

test.describe('Dify Page - App Form Modal', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dify')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('Register App button opens modal', async ({ page }) => {
    const btn = page.getByRole('button', { name: /Register App/i })
    const isDisabled = await btn.isDisabled()
    if (!isDisabled) {
      await btn.click()
      await expect(page.getByText('Register Dify App')).toBeVisible()
      console.log('✅ App modal opens')
    } else {
      console.log('⊘ Register App button is disabled (no instances)')
    }
  })

  test('app modal has instance dropdown, App ID, App Name, App Type fields', async ({ page }) => {
    const btn = page.getByRole('button', { name: /Register App/i })
    if (await btn.isDisabled()) {
      console.log('⊘ Skipping - button disabled')
      return
    }
    await btn.click()
    await expect(page.getByText('Instance *')).toBeVisible()
    await expect(page.getByText('App ID *')).toBeVisible()
    await expect(page.getByText('App Name')).toBeVisible()
    await expect(page.getByText('App Type')).toBeVisible()
    console.log('✅ All app form fields visible')
  })

  test('app type select has 4 options', async ({ page }) => {
    const btn = page.getByRole('button', { name: /Register App/i })
    if (await btn.isDisabled()) {
      console.log('⊘ Skipping - button disabled')
      return
    }
    await btn.click()
    // The app type select is the second select in the modal (first is instance)
    const selects = page.locator('.fixed select')
    const appTypeSelect = selects.last()
    const options = appTypeSelect.locator('option')
    const texts = await options.allTextContents()
    console.log(`App type options: ${texts.join(', ')}`)
    expect(texts).toContain('Workflow')
    expect(texts).toContain('Chatbot')
    expect(texts).toContain('Agent')
    expect(texts).toContain('Chatflow')
  })

  test('Cancel closes app modal', async ({ page }) => {
    const btn = page.getByRole('button', { name: /Register App/i })
    if (await btn.isDisabled()) {
      console.log('⊘ Skipping - button disabled')
      return
    }
    await btn.click()
    await expect(page.getByText('Register Dify App')).toBeVisible()
    await page.locator('.fixed').getByRole('button', { name: /Cancel/i }).click()
    await expect(page.getByText('Register Dify App')).not.toBeVisible()
    console.log('✅ App modal closed')
  })
})

test.describe('Dify Page - Demo Data Display', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dify')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('instances list or empty state shown', async ({ page }) => {
    const hasInstances = await page.getByText('Active').first().isVisible().catch(() => false)
    const isEmpty = await page.getByText('No Dify instances connected').isVisible().catch(() => false)
    console.log(`Instances visible: ${hasInstances}, Empty state: ${isEmpty}`)
    expect(hasInstances || isEmpty).toBe(true)
  })

  test('instances show badges and stats', async ({ page }) => {
    const hasActive = await page.getByText('Active').first().isVisible().catch(() => false)
    if (hasActive) {
      const hasRuns = await page.getByText(/runs/).first().isVisible().catch(() => false)
      const hasTokens = await page.getByText(/tokens/).first().isVisible().catch(() => false)
      console.log(`Active badge: ${hasActive}, Runs: ${hasRuns}, Tokens: ${hasTokens}`)
      expect(hasRuns || hasTokens).toBe(true)
    } else {
      console.log('⊘ No instances to check badges/stats')
    }
  })
})
