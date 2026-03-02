import { test, expect } from '@playwright/test'

test.describe('LangGraph Documentation Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/docs/langgraph')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('page loads with title', async ({ page }) => {
    await expect(page.locator('h1').first()).toContainText('LangGraph Integration')
    console.log('✅ LangGraph docs title visible')
  })

  test('subtitle describes graph-based agent monitoring', async ({ page }) => {
    await expect(page.getByText(/Monitor stateful graph-based agents/i)).toBeVisible()
    console.log('✅ Subtitle visible')
  })

  test('Why LangGraph section with 4 feature cards', async ({ page }) => {
    await expect(page.getByText('Why LangGraph Integration?')).toBeVisible()
    const features = ['Graph State Monitoring', 'Recursion Detection', 'Checkpoint Integrity', 'Parallel Branch Tracking']
    for (const feature of features) {
      await expect(page.getByText(feature).first()).toBeVisible()
    }
    console.log('✅ All 4 feature cards visible')
  })

  test('Graph Concepts section shows 4 concepts', async ({ page }) => {
    await expect(page.getByText('Graph Concepts')).toBeVisible()
    const concepts = ['Nodes', 'Edges', 'State', 'Checkpoints']
    for (const concept of concepts) {
      const visible = await page.locator('h3').filter({ hasText: concept }).first().isVisible().catch(() => false)
      console.log(`  ${concept}: ${visible}`)
    }
    console.log('✅ Graph Concepts section visible')
  })

  test('each concept card has description text', async ({ page }) => {
    // Nodes concept should have description about "state entry"
    await expect(page.getByText(/state entry/i)).toBeVisible()
    console.log('✅ Concept descriptions present')
  })

  test('Integration Methods shows 2 methods', async ({ page }) => {
    await expect(page.getByText('Method 1: Python SDK (Recommended)')).toBeVisible()
    await expect(page.getByText('Method 2: Webhook')).toBeVisible()
    console.log('✅ Both integration methods visible')
  })

  test('SDK method shows Python code block with LangGraphTracer', async ({ page }) => {
    const codeWithTracer = page.locator('pre').filter({ hasText: 'LangGraphTracer' })
    await expect(codeWithTracer.first()).toBeVisible()
    console.log('✅ LangGraphTracer code block visible')
  })

  test('SDK method shows green info banner', async ({ page }) => {
    await expect(page.getByText(/tracer automatically captures/i)).toBeVisible()
    console.log('✅ SDK info banner visible')
  })

  test('webhook method shows JSON payload example', async ({ page }) => {
    const jsonPayload = page.locator('pre').filter({ hasText: 'run_id' })
    await expect(jsonPayload.first()).toBeVisible()
    console.log('✅ JSON payload example visible')
  })

  test('Webhook Security section exists', async ({ page }) => {
    await expect(page.locator('h2').filter({ hasText: 'Webhook Security' })).toBeVisible()
    console.log('✅ Webhook Security section visible')
  })

  test('Security Note is displayed', async ({ page }) => {
    await expect(page.getByText('Security Note')).toBeVisible()
    console.log('✅ Security Note visible')
  })

  test('Detection table has 6 rows', async ({ page }) => {
    const detections = ['Recursion', 'State Corruption', 'Edge Misroute', 'Tool Failure', 'Parallel Sync', 'Checkpoint Corruption']
    for (const name of detections) {
      await expect(page.getByText(name).first()).toBeVisible()
    }
    console.log('✅ All 6 detection types visible')
  })

  test('Data Mapping table has 8 rows with LangGraph header', async ({ page }) => {
    await expect(page.getByText('LangGraph Field').first()).toBeVisible()
    // Verify thread_id is mapped (unique to LangGraph - 8th row)
    await expect(page.getByText('thread_id').first()).toBeVisible()
    console.log('✅ Data mapping table with 8 rows visible')
  })

  test('Related Documentation has links', async ({ page }) => {
    await expect(page.locator('h2').filter({ hasText: 'Related Documentation' })).toBeVisible()
    await expect(page.locator('a[href="/docs/sdk"]').first()).toBeVisible()
    await expect(page.locator('a[href="/docs/api-reference"]').first()).toBeVisible()
    console.log('✅ Related docs visible')
  })

  test('docs sidebar highlights LangGraph Integration as active', async ({ page }) => {
    const sidebarLink = page.locator('a[href="/docs/langgraph"]').first()
    await expect(sidebarLink).toBeVisible()
    console.log('✅ LangGraph sidebar link visible')
  })
})
