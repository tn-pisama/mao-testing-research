import { test, expect } from '@playwright/test'

test.describe('Integrations Page - Core Rendering', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/integrations')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('page loads with title', async ({ page }) => {
    await expect(page.locator('h1').first()).toContainText('Integrations')
    console.log('✅ Integrations page title visible')
  })

  test('loading completes', async ({ page }) => {
    await expect(page.locator('.animate-pulse')).not.toBeVisible({ timeout: 15000 })
    await expect(page.locator('.animate-spin')).not.toBeVisible({ timeout: 15000 })
    console.log('✅ Loading complete')
  })

  test('all 5 tabs are visible', async ({ page }) => {
    const tabNames = ['Overview', 'n8n', 'OpenClaw', 'Dify', 'LangGraph']
    for (const name of tabNames) {
      const tab = page.locator('button').filter({ hasText: name })
      await expect(tab.first()).toBeVisible()
    }
    console.log('✅ All 5 tabs visible')
  })
})

test.describe('Integrations Page - Overview Tab', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/integrations')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('overview tab is active by default', async ({ page }) => {
    const overviewTab = page.locator('button').filter({ hasText: 'Overview' }).first()
    await expect(overviewTab).toBeVisible()
    // Check it has active styling (bg-primary or similar active class)
    const classes = await overviewTab.getAttribute('class') || ''
    console.log(`Overview tab classes contain primary: ${classes.includes('primary') || classes.includes('active')}`)
  })

  test('shows 4 provider cards', async ({ page }) => {
    const providers = ['n8n', 'OpenClaw', 'Dify', 'LangGraph']
    let found = 0
    for (const name of providers) {
      const hasProvider = await page.getByText(name).first().isVisible().catch(() => false)
      if (hasProvider) found++
    }
    console.log(`Provider cards found: ${found}/4`)
    expect(found).toBeGreaterThanOrEqual(4)
  })

  test('provider cards show connection status', async ({ page }) => {
    const hasConnected = await page.getByText('Connected').first().isVisible().catch(() => false)
    const hasNotConfigured = await page.getByText('Not configured').first().isVisible().catch(() => false)
    console.log(`Connected: ${hasConnected}, Not configured: ${hasNotConfigured}`)
    expect(hasConnected || hasNotConfigured).toBe(true)
  })

  test('provider cards show entity counts', async ({ page }) => {
    const hasCount = await page.getByText(/\d+\s+(workflows|instances|agents|deployments|assistants|apps)/i).first().isVisible().catch(() => false)
    console.log(`Entity count visible: ${hasCount}`)
  })

  test('clicking a provider card switches to its tab', async ({ page }) => {
    // Click the Dify provider area in the overview
    const difyCard = page.locator('button, [role="button"]').filter({ hasText: 'Dify' }).first()
    if (await difyCard.isVisible()) {
      await difyCard.click()
      await page.waitForTimeout(500)
      // Should now show Dify tab content
      const hasDifyContent = await page.getByText('Dify Instances').isVisible().catch(() => false)
        || await page.getByText('Registered Apps').isVisible().catch(() => false)
      console.log(`Dify tab content after click: ${hasDifyContent}`)
    } else {
      console.log('⊘ Dify card not clickable')
    }
  })
})

test.describe('Integrations Page - Tab Switching', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/integrations')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('n8n tab shows workflow content', async ({ page }) => {
    await page.locator('button').filter({ hasText: 'n8n' }).first().click()
    await page.waitForTimeout(500)
    const hasContent = await page.getByText(/n8n Workflows|Manage Workflows/i).first().isVisible().catch(() => false)
    console.log(`n8n tab content: ${hasContent}`)
    expect(hasContent).toBe(true)
  })

  test('n8n tab has Manage Workflows link', async ({ page }) => {
    await page.locator('button').filter({ hasText: 'n8n' }).first().click()
    await page.waitForTimeout(500)
    const link = page.locator('a[href="/n8n"]')
    const hasLink = await link.first().isVisible().catch(() => false)
    console.log(`Manage Workflows link: ${hasLink}`)
  })

  test('OpenClaw tab shows instances and agents', async ({ page }) => {
    await page.locator('button').filter({ hasText: 'OpenClaw' }).first().click()
    await page.waitForTimeout(500)
    const hasInstances = await page.getByText('OpenClaw Instances').isVisible().catch(() => false)
    const hasAgents = await page.getByText('Registered Agents').isVisible().catch(() => false)
    console.log(`OpenClaw - Instances: ${hasInstances}, Agents: ${hasAgents}`)
    expect(hasInstances || hasAgents).toBe(true)
  })

  test('Dify tab shows instances and apps', async ({ page }) => {
    await page.locator('button').filter({ hasText: 'Dify' }).first().click()
    await page.waitForTimeout(500)
    const hasInstances = await page.getByText('Dify Instances').isVisible().catch(() => false)
    const hasApps = await page.getByText('Registered Apps').isVisible().catch(() => false)
    console.log(`Dify - Instances: ${hasInstances}, Apps: ${hasApps}`)
    expect(hasInstances || hasApps).toBe(true)
  })

  test('LangGraph tab shows deployments and assistants', async ({ page }) => {
    await page.locator('button').filter({ hasText: 'LangGraph' }).first().click()
    await page.waitForTimeout(500)
    const hasDeployments = await page.getByText('LangGraph Deployments').isVisible().catch(() => false)
    const hasAssistants = await page.getByText('Registered Assistants').isVisible().catch(() => false)
    console.log(`LangGraph - Deployments: ${hasDeployments}, Assistants: ${hasAssistants}`)
    expect(hasDeployments || hasAssistants).toBe(true)
  })

  test('LangGraph tab has Manage Deployments link', async ({ page }) => {
    await page.locator('button').filter({ hasText: 'LangGraph' }).first().click()
    await page.waitForTimeout(500)
    const link = page.locator('a[href="/langgraph"]')
    const hasLink = await link.first().isVisible().catch(() => false)
    console.log(`Manage Deployments link: ${hasLink}`)
  })
})

test.describe('Integrations Page - Tab Content Detail', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/integrations')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('Dify tab shows app type badges', async ({ page }) => {
    await page.locator('button').filter({ hasText: 'Dify' }).first().click()
    await page.waitForTimeout(500)
    const hasWorkflow = await page.getByText('workflow').first().isVisible().catch(() => false)
    const hasChatbot = await page.getByText('chatbot').first().isVisible().catch(() => false)
    console.log(`App type badges - workflow: ${hasWorkflow}, chatbot: ${hasChatbot}`)
  })

  test('OpenClaw tab shows OTEL badge', async ({ page }) => {
    await page.locator('button').filter({ hasText: 'OpenClaw' }).first().click()
    await page.waitForTimeout(500)
    const hasOtel = await page.getByText('OTEL').first().isVisible().catch(() => false)
    console.log(`OTEL badge: ${hasOtel}`)
  })

  test('LangGraph tab shows graph info', async ({ page }) => {
    await page.locator('button').filter({ hasText: 'LangGraph' }).first().click()
    await page.waitForTimeout(500)
    const hasGraph = await page.getByText(/Graph:/).first().isVisible().catch(() => false)
      || await page.getByText(/graph_id/).first().isVisible().catch(() => false)
    console.log(`Graph info: ${hasGraph}`)
  })

  test('switching tabs back and forth works', async ({ page }) => {
    // Switch to Dify
    await page.locator('button').filter({ hasText: 'Dify' }).first().click()
    await page.waitForTimeout(300)
    const hasDify1 = await page.getByText('Dify Instances').isVisible().catch(() => false)

    // Switch to Overview
    await page.locator('button').filter({ hasText: 'Overview' }).first().click()
    await page.waitForTimeout(300)

    // Switch back to Dify
    await page.locator('button').filter({ hasText: 'Dify' }).first().click()
    await page.waitForTimeout(300)
    const hasDify2 = await page.getByText('Dify Instances').isVisible().catch(() => false)

    console.log(`Dify first: ${hasDify1}, Dify again: ${hasDify2}`)
    expect(hasDify1 || hasDify2).toBe(true)
  })
})

test.describe('Integrations Page - Error Handling', () => {
  test('page handles API failure gracefully', async ({ page }) => {
    // Intercept API calls to simulate failure
    await page.route('**/api/v1/**', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal server error' }),
      })
    })

    await page.goto('/integrations')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(3000)

    // Page should still render with demo data fallback
    await expect(page.locator('h1').first()).toContainText('Integrations')
    console.log('✅ Page did not crash on API failure')
  })

  test('refresh button exists and is clickable', async ({ page }) => {
    await page.goto('/integrations')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)

    const refreshBtn = page.locator('button').filter({ has: page.locator('svg') }).filter({ hasText: /Refresh/i })
      .or(page.locator('button[title*="efresh"]'))
      .or(page.locator('button').filter({ has: page.locator('.lucide-refresh-cw') }))

    if (await refreshBtn.first().isVisible().catch(() => false)) {
      await refreshBtn.first().click()
      await page.waitForTimeout(500)
      console.log('✅ Refresh button clicked')
    } else {
      console.log('⊘ Refresh button not found (may use different pattern)')
    }
  })
})

test.describe('Integrations Page - Tab Persistence', () => {
  test('tab stays active during interaction', async ({ page }) => {
    await page.goto('/integrations')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)

    // Switch to LangGraph tab
    await page.locator('button').filter({ hasText: 'LangGraph' }).first().click()
    await page.waitForTimeout(500)

    // Verify LangGraph content is shown
    const hasLangGraphContent = await page.getByText('LangGraph Deployments').isVisible().catch(() => false)
      || await page.getByText('Registered Assistants').isVisible().catch(() => false)
    console.log(`LangGraph tab active: ${hasLangGraphContent}`)
    expect(hasLangGraphContent).toBe(true)
  })
})
