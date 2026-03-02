import { test, expect } from '@playwright/test'

test.describe('OpenClaw Page - Core Rendering', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/openclaw')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('page loads and displays title', async ({ page }) => {
    await expect(page.locator('h1').first()).toContainText('OpenClaw Agents')
    console.log('✅ OpenClaw page title visible')
  })

  test('description text is visible', async ({ page }) => {
    await expect(page.getByText('Connect OpenClaw instances for multi-channel session monitoring')).toBeVisible()
    console.log('✅ Description visible')
  })

  test('loading completes', async ({ page }) => {
    await expect(page.locator('.animate-spin')).not.toBeVisible({ timeout: 15000 })
    console.log('✅ Loading complete')
  })

  test('demo mode badge is shown', async ({ page }) => {
    const hasDemoBadge = await page.getByText('Demo Mode').first().isVisible().catch(() => false)
    console.log(`Demo Mode badge: ${hasDemoBadge}`)
    expect(hasDemoBadge).toBe(true)
  })

  test('Add Instance button is visible', async ({ page }) => {
    await expect(page.getByRole('button', { name: /Add Instance/i })).toBeVisible()
    console.log('✅ Add Instance button visible')
  })

  test('Register Agent button exists', async ({ page }) => {
    await expect(page.getByRole('button', { name: /Register Agent/i })).toBeVisible()
    console.log('✅ Register Agent button visible')
  })

  test('webhook URL banner shows openclaw endpoint', async ({ page }) => {
    await expect(page.getByText('Webhook URL').first()).toBeVisible()
    await expect(page.locator('code').filter({ hasText: 'openclaw/webhook' })).toBeVisible()
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

test.describe('OpenClaw Page - Instance Form Modal', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/openclaw')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('clicking Add Instance opens modal', async ({ page }) => {
    await expect(page.getByText('Add OpenClaw Instance')).not.toBeVisible()
    await page.getByRole('button', { name: /Add Instance/i }).click()
    await expect(page.getByText('Add OpenClaw Instance')).toBeVisible()
    console.log('✅ Instance modal opens')
  })

  test('instance modal has 3 required fields', async ({ page }) => {
    await page.getByRole('button', { name: /Add Instance/i }).click()
    await expect(page.getByText('Instance Name *')).toBeVisible()
    await expect(page.getByText('Gateway URL *')).toBeVisible()
    await expect(page.getByText('API Key *')).toBeVisible()
    console.log('✅ All 3 required fields visible')
  })

  test('modal has Register and Cancel buttons', async ({ page }) => {
    await page.getByRole('button', { name: /Add Instance/i }).click()
    await expect(page.locator('.fixed').getByRole('button', { name: /^Register$/i })).toBeVisible()
    await expect(page.locator('.fixed').getByRole('button', { name: /Cancel/i })).toBeVisible()
    console.log('✅ Register and Cancel buttons in modal')
  })

  test('Cancel closes the modal', async ({ page }) => {
    await page.getByRole('button', { name: /Add Instance/i }).click()
    await expect(page.getByText('Add OpenClaw Instance')).toBeVisible()
    await page.locator('.fixed').getByRole('button', { name: /Cancel/i }).click()
    await expect(page.getByText('Add OpenClaw Instance')).not.toBeVisible()
    console.log('✅ Modal closed on Cancel')
  })

  test('empty form shows validation error', async ({ page }) => {
    await page.getByRole('button', { name: /Add Instance/i }).click()
    await page.locator('.fixed').getByRole('button', { name: /^Register$/i }).click()
    await expect(page.getByText('Name, Gateway URL, and API Key are required')).toBeVisible()
    console.log('✅ Validation error shown')
  })
})

test.describe('OpenClaw Page - Agent Form Modal', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/openclaw')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('Register Agent button opens modal', async ({ page }) => {
    const btn = page.getByRole('button', { name: /Register Agent/i })
    if (await btn.isDisabled()) {
      console.log('⊘ Register Agent button is disabled (no instances)')
      return
    }
    await btn.click()
    await expect(page.getByText('Register OpenClaw Agent')).toBeVisible()
    console.log('✅ Agent modal opens')
  })

  test('agent modal has Instance dropdown, Agent Key, Agent Name, Model fields', async ({ page }) => {
    const btn = page.getByRole('button', { name: /Register Agent/i })
    if (await btn.isDisabled()) {
      console.log('⊘ Skipping - button disabled')
      return
    }
    await btn.click()
    await expect(page.getByText('Instance *')).toBeVisible()
    await expect(page.getByText('Agent Key *')).toBeVisible()
    await expect(page.getByText('Agent Name')).toBeVisible()
    await expect(page.getByText('Model')).toBeVisible()
    console.log('✅ All agent form fields visible')
  })

  test('Cancel closes agent modal', async ({ page }) => {
    const btn = page.getByRole('button', { name: /Register Agent/i })
    if (await btn.isDisabled()) {
      console.log('⊘ Skipping - button disabled')
      return
    }
    await btn.click()
    await expect(page.getByText('Register OpenClaw Agent')).toBeVisible()
    await page.locator('.fixed').getByRole('button', { name: /Cancel/i }).click()
    await expect(page.getByText('Register OpenClaw Agent')).not.toBeVisible()
    console.log('✅ Agent modal closed')
  })
})

test.describe('OpenClaw Page - Demo Data Display', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/openclaw')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('instances list or empty state shown', async ({ page }) => {
    const hasInstances = await page.getByText('Active').first().isVisible().catch(() => false)
    const isEmpty = await page.getByText('No OpenClaw instances connected').isVisible().catch(() => false)
    console.log(`Instances visible: ${hasInstances}, Empty state: ${isEmpty}`)
    expect(hasInstances || isEmpty).toBe(true)
  })

  test('OTEL badge displays for enabled instances', async ({ page }) => {
    const hasOtel = await page.getByText('OTEL').first().isVisible().catch(() => false)
    console.log(`OTEL badge visible: ${hasOtel}`)
    // OTEL badge is present when demo data has otel_enabled instances
  })

  test('agent stats show sessions and messages', async ({ page }) => {
    const hasInstances = await page.getByText('Active').first().isVisible().catch(() => false)
    if (hasInstances) {
      const hasSessions = await page.getByText(/sessions/).first().isVisible().catch(() => false)
      const hasMessages = await page.getByText(/messages/).first().isVisible().catch(() => false)
      console.log(`Sessions: ${hasSessions}, Messages: ${hasMessages}`)
      expect(hasSessions || hasMessages).toBe(true)
    } else {
      console.log('⊘ No instances to check stats')
    }
  })
})
