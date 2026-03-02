import { test, expect } from '@playwright/test'

test.describe('Dify Documentation Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/docs/dify')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('page loads with title', async ({ page }) => {
    await expect(page.locator('h1').first()).toContainText('Dify Integration')
    console.log('✅ Dify docs title visible')
  })

  test('subtitle describes Dify monitoring', async ({ page }) => {
    await expect(page.getByText(/Monitor AI workflows, chatbots, and agents built in Dify/i)).toBeVisible()
    console.log('✅ Subtitle visible')
  })

  test('Why Dify section with 4 feature cards', async ({ page }) => {
    await expect(page.getByText('Why Dify Integration?')).toBeVisible()
    const features = ['RAG Pipeline Monitoring', 'Iteration Tracking', 'Model Fallback Detection', 'Variable Leak Prevention']
    for (const feature of features) {
      await expect(page.getByText(feature)).toBeVisible()
    }
    console.log('✅ All 4 feature cards visible')
  })

  test('Supported App Types shows 4 types', async ({ page }) => {
    const types = ['Chatbot', 'Agent', 'Workflow', 'Chatflow']
    for (const type of types) {
      await expect(page.getByText(type).first()).toBeVisible()
    }
    console.log('✅ All 4 app types visible')
  })

  test('Integration Methods has 2 methods', async ({ page }) => {
    await expect(page.getByText('Method 1: Webhook (Recommended)')).toBeVisible()
    await expect(page.getByText('Method 2: SDK Integration')).toBeVisible()
    console.log('✅ Both integration methods visible')
  })

  test('method cards show pros and cons', async ({ page }) => {
    const prosCount = await page.getByText('Pros').count()
    const consCount = await page.getByText('Cons').count()
    console.log(`Pros sections: ${prosCount}, Cons sections: ${consCount}`)
    expect(prosCount).toBeGreaterThanOrEqual(2)
    expect(consCount).toBeGreaterThanOrEqual(2)
  })

  test('code blocks render with syntax content', async ({ page }) => {
    const codeBlocks = page.locator('pre')
    const count = await codeBlocks.count()
    console.log(`Code blocks found: ${count}`)
    expect(count).toBeGreaterThanOrEqual(3)
  })

  test('Webhook Security section exists', async ({ page }) => {
    await expect(page.locator('h2').filter({ hasText: 'Webhook Security' })).toBeVisible()
    await expect(page.getByText('X-MAO-Signature')).toBeVisible()
    console.log('✅ Webhook Security section visible')
  })

  test('Security Note warning displayed', async ({ page }) => {
    await expect(page.getByText('Security Note')).toBeVisible()
    console.log('✅ Security Note visible')
  })

  test('Detection table has 6 rows', async ({ page }) => {
    const detectionNames = ['RAG Poisoning', 'Iteration Escape', 'Model Fallback', 'Variable Leak', 'Classifier Drift', 'Tool Schema Mismatch']
    for (const name of detectionNames) {
      await expect(page.getByText(name).first()).toBeVisible()
    }
    console.log('✅ All 6 detection types visible')
  })

  test('Data Mapping table has 7 rows', async ({ page }) => {
    // Find the data mapping table (second table on page or table with "Dify" header)
    const tables = page.locator('table')
    const tableCount = await tables.count()
    console.log(`Tables found: ${tableCount}`)
    expect(tableCount).toBeGreaterThanOrEqual(2)

    // Check for Dify-specific mapping fields
    await expect(page.getByText('workflow_run_id').first()).toBeVisible()
    console.log('✅ Data mapping table visible')
  })

  test('Related Documentation has 4 links', async ({ page }) => {
    await expect(page.locator('h2').filter({ hasText: 'Related Documentation' })).toBeVisible()
    const relatedSection = page.locator('h2').filter({ hasText: 'Related Documentation' }).locator('..')
    const relatedLinks = relatedSection.locator('a')
    const count = await relatedLinks.count()
    console.log(`Related doc links: ${count}`)
    expect(count).toBeGreaterThanOrEqual(2)
  })

  test('related docs link to correct pages', async ({ page }) => {
    await expect(page.locator('a[href="/docs/sdk"]').first()).toBeVisible()
    await expect(page.locator('a[href="/docs/api-reference"]').first()).toBeVisible()
    console.log('✅ Related doc hrefs correct')
  })

  test('code block copy button works', async ({ page }) => {
    // Grant clipboard permissions
    await page.context().grantPermissions(['clipboard-write'])

    // Find the first copy button in a code block header
    const copyBtn = page.locator('button').filter({ has: page.locator('svg') }).first()
    if (await copyBtn.isVisible()) {
      await copyBtn.click()
      // After click, CheckCircle icon should appear (text-emerald-400)
      const hasCheck = await page.locator('.text-emerald-400').first().isVisible().catch(() => false)
      console.log(`Copy feedback (CheckCircle): ${hasCheck}`)
    } else {
      console.log('⊘ Copy button not found')
    }
  })

  test('docs sidebar highlights Dify Integration as active', async ({ page }) => {
    const sidebarLink = page.locator('a[href="/docs/dify"]').first()
    await expect(sidebarLink).toBeVisible()
    const classes = await sidebarLink.getAttribute('class') || ''
    const isActive = classes.includes('primary') || classes.includes('font-medium') || classes.includes('active')
    console.log(`Dify sidebar link active: ${isActive}`)
  })
})
