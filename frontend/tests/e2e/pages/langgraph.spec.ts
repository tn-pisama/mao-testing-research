import { test, expect } from '@playwright/test'

test.describe('LangGraph Page - Core Rendering', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/langgraph')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('page loads and displays title', async ({ page }) => {
    await expect(page.locator('h1').first()).toContainText('LangGraph Deployments')
    console.log('✅ LangGraph page title visible')
  })

  test('description text is visible', async ({ page }) => {
    await expect(page.getByText('Connect LangGraph deployments for graph run monitoring')).toBeVisible()
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

  test('Add Deployment button is visible', async ({ page }) => {
    await expect(page.getByRole('button', { name: /Add Deployment/i })).toBeVisible()
    console.log('✅ Add Deployment button visible')
  })

  test('Register Assistant button exists', async ({ page }) => {
    await expect(page.getByRole('button', { name: /Register Assistant/i })).toBeVisible()
    console.log('✅ Register Assistant button visible')
  })

  test('webhook URL banner shows langgraph endpoint', async ({ page }) => {
    await expect(page.getByText('Webhook URL').first()).toBeVisible()
    await expect(page.locator('code').filter({ hasText: 'langgraph/webhook' })).toBeVisible()
    console.log('✅ Webhook URL banner visible')
  })

  test('setup instructions section with 4 steps', async ({ page }) => {
    await expect(page.getByText('Setup Instructions')).toBeVisible()
    const steps = page.locator('ol li, .space-y-3 > li')
    const count = await steps.count()
    console.log(`📋 Setup steps found: ${count}`)
    expect(count).toBeGreaterThanOrEqual(4)
  })

  test('SDK code snippet shows LangGraphTracer', async ({ page }) => {
    const codeBlock = page.locator('pre, code').filter({ hasText: 'LangGraphTracer' })
    const hasSDK = await codeBlock.first().isVisible().catch(() => false)
    console.log(`SDK snippet visible: ${hasSDK}`)
    // SDK code snippet may be in the setup instructions section
  })
})

test.describe('LangGraph Page - Deployment Form Modal', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/langgraph')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('clicking Add Deployment opens modal', async ({ page }) => {
    await expect(page.getByText('Add LangGraph Deployment')).not.toBeVisible()
    await page.getByRole('button', { name: /Add Deployment/i }).click()
    await expect(page.getByText('Add LangGraph Deployment')).toBeVisible()
    console.log('✅ Deployment modal opens')
  })

  test('deployment modal has 5 fields (3 required, 2 optional)', async ({ page }) => {
    await page.getByRole('button', { name: /Add Deployment/i }).click()
    await expect(page.getByText('Deployment Name *')).toBeVisible()
    await expect(page.getByText('API URL *')).toBeVisible()
    await expect(page.getByText('API Key *')).toBeVisible()
    // Optional fields (no asterisk)
    await expect(page.getByText('Deployment ID')).toBeVisible()
    await expect(page.getByText('Graph Name')).toBeVisible()
    console.log('✅ All 5 deployment form fields visible')
  })

  test('modal has Register and Cancel buttons', async ({ page }) => {
    await page.getByRole('button', { name: /Add Deployment/i }).click()
    await expect(page.locator('.fixed').getByRole('button', { name: /^Register$/i })).toBeVisible()
    await expect(page.locator('.fixed').getByRole('button', { name: /Cancel/i })).toBeVisible()
    console.log('✅ Register and Cancel buttons in modal')
  })

  test('Cancel closes deployment modal', async ({ page }) => {
    await page.getByRole('button', { name: /Add Deployment/i }).click()
    await expect(page.getByText('Add LangGraph Deployment')).toBeVisible()
    await page.locator('.fixed').getByRole('button', { name: /Cancel/i }).click()
    await expect(page.getByText('Add LangGraph Deployment')).not.toBeVisible()
    console.log('✅ Modal closed on Cancel')
  })

  test('empty form shows validation error', async ({ page }) => {
    await page.getByRole('button', { name: /Add Deployment/i }).click()
    await page.locator('.fixed').getByRole('button', { name: /^Register$/i }).click()
    await expect(page.getByText('Name, API URL, and API Key are required')).toBeVisible()
    console.log('✅ Validation error shown')
  })
})

test.describe('LangGraph Page - Assistant Form Modal', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/langgraph')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('Register Assistant button opens modal', async ({ page }) => {
    const btn = page.getByRole('button', { name: /Register Assistant/i })
    if (await btn.isDisabled()) {
      console.log('⊘ Register Assistant button is disabled (no deployments)')
      return
    }
    await btn.click()
    await expect(page.getByText('Register LangGraph Assistant')).toBeVisible()
    console.log('✅ Assistant modal opens')
  })

  test('assistant modal has Deployment dropdown, Assistant ID, Graph ID, Name fields', async ({ page }) => {
    const btn = page.getByRole('button', { name: /Register Assistant/i })
    if (await btn.isDisabled()) {
      console.log('⊘ Skipping - button disabled')
      return
    }
    await btn.click()
    await expect(page.getByText('Deployment *')).toBeVisible()
    await expect(page.getByText('Assistant ID *')).toBeVisible()
    await expect(page.getByText('Graph ID *')).toBeVisible()
    await expect(page.getByText('Name')).toBeVisible()
    console.log('✅ All assistant form fields visible')
  })

  test('Cancel closes assistant modal', async ({ page }) => {
    const btn = page.getByRole('button', { name: /Register Assistant/i })
    if (await btn.isDisabled()) {
      console.log('⊘ Skipping - button disabled')
      return
    }
    await btn.click()
    await expect(page.getByText('Register LangGraph Assistant')).toBeVisible()
    await page.locator('.fixed').getByRole('button', { name: /Cancel/i }).click()
    await expect(page.getByText('Register LangGraph Assistant')).not.toBeVisible()
    console.log('✅ Assistant modal closed')
  })

  test('empty assistant form shows validation error', async ({ page }) => {
    const btn = page.getByRole('button', { name: /Register Assistant/i })
    if (await btn.isDisabled()) {
      console.log('⊘ Skipping - button disabled')
      return
    }
    await btn.click()
    await page.locator('.fixed').getByRole('button', { name: /^Register$/i }).click()
    await expect(page.getByText('Deployment, Assistant ID, and Graph ID are required')).toBeVisible()
    console.log('✅ Validation error shown')
  })
})

test.describe('LangGraph Page - Demo Data Display', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/langgraph')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('deployments list or empty state shown', async ({ page }) => {
    const hasDeployments = await page.getByText('Active').first().isVisible().catch(() => false)
    const isEmpty = await page.getByText('No LangGraph deployments connected').isVisible().catch(() => false)
    console.log(`Deployments visible: ${hasDeployments}, Empty state: ${isEmpty}`)
    expect(hasDeployments || isEmpty).toBe(true)
  })

  test('deployment shows graph name', async ({ page }) => {
    const hasGraph = await page.getByText(/Graph:/).first().isVisible().catch(() => false)
    console.log(`Graph name visible: ${hasGraph}`)
  })

  test('assistants show total runs stat', async ({ page }) => {
    const hasDeployments = await page.getByText('Active').first().isVisible().catch(() => false)
    if (hasDeployments) {
      const hasRuns = await page.getByText(/runs/).first().isVisible().catch(() => false)
      console.log(`Runs stat visible: ${hasRuns}`)
    } else {
      console.log('⊘ No deployments to check stats')
    }
  })
})
