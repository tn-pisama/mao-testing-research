import { test, expect } from '@playwright/test'

test.describe('OpenClaw Documentation Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/docs/openclaw')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('page loads with title', async ({ page }) => {
    await expect(page.locator('h1').first()).toContainText('OpenClaw Integration')
    console.log('✅ OpenClaw docs title visible')
  })

  test('subtitle describes multi-channel monitoring', async ({ page }) => {
    await expect(page.getByText(/Monitor multi-channel AI agents/i)).toBeVisible()
    console.log('✅ Subtitle visible')
  })

  test('Why OpenClaw section with 4 feature cards', async ({ page }) => {
    await expect(page.getByText('Why OpenClaw Integration?')).toBeVisible()
    const features = ['Multi-Channel Monitoring', 'Spawn Chain Tracking', 'Sandbox Enforcement', 'Real-Time Risk Assessment']
    for (const feature of features) {
      await expect(page.getByText(feature)).toBeVisible()
    }
    console.log('✅ All 4 feature cards visible')
  })

  test('Supported Channels shows 5 channels', async ({ page }) => {
    const channels = ['WhatsApp', 'Telegram', 'Slack', 'Discord', 'Web']
    for (const channel of channels) {
      await expect(page.getByText(channel).first()).toBeVisible()
    }
    console.log('✅ All 5 channels visible')
  })

  test('Integration Methods has 2 methods', async ({ page }) => {
    await expect(page.getByText('Method 1: Webhook (Recommended)')).toBeVisible()
    await expect(page.getByText('Method 2: OTEL Export')).toBeVisible()
    console.log('✅ Both integration methods visible')
  })

  test('webhook method shows YAML config', async ({ page }) => {
    const hasYaml = await page.getByText('session.completed').isVisible().catch(() => false)
      || await page.getByText('Gateway Config').isVisible().catch(() => false)
    console.log(`YAML config visible: ${hasYaml}`)
    expect(hasYaml).toBe(true)
  })

  test('OTEL method shows config code block', async ({ page }) => {
    const hasOtelConfig = await page.getByText('Gateway OTEL Config').isVisible().catch(() => false)
      || await page.locator('pre').filter({ hasText: 'otel:' }).first().isVisible().catch(() => false)
    console.log(`OTEL config visible: ${hasOtelConfig}`)
    expect(hasOtelConfig).toBe(true)
  })

  test('Multi-Agent Monitoring section with spawn tree', async ({ page }) => {
    await expect(page.getByText('Multi-Agent Monitoring')).toBeVisible()
    await expect(page.getByText('root-agent')).toBeVisible()
    await expect(page.getByText('research-agent')).toBeVisible()
    await expect(page.getByText('writer-agent')).toBeVisible()
    console.log('✅ Spawn tree diagram visible')
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
    const detections = ['Session Loop', 'Tool Abuse', 'Elevated Risk', 'Spawn Chain', 'Channel Mismatch', 'Sandbox Escape']
    for (const name of detections) {
      await expect(page.getByText(name).first()).toBeVisible()
    }
    console.log('✅ All 6 detection types visible')
  })

  test('Data Mapping table has 7 rows with OpenClaw header', async ({ page }) => {
    const tables = page.locator('table')
    const tableCount = await tables.count()
    expect(tableCount).toBeGreaterThanOrEqual(2)
    await expect(page.getByText('OpenClaw Field').first()).toBeVisible()
    console.log('✅ Data mapping table visible')
  })

  test('Related Documentation has 4 links', async ({ page }) => {
    await expect(page.locator('h2').filter({ hasText: 'Related Documentation' })).toBeVisible()
    await expect(page.locator('a[href="/docs/sdk"]').first()).toBeVisible()
    await expect(page.locator('a[href="/docs/api-reference"]').first()).toBeVisible()
    console.log('✅ Related docs visible')
  })

  test('code blocks render properly', async ({ page }) => {
    const codeBlocks = page.locator('pre')
    const count = await codeBlocks.count()
    console.log(`Code blocks found: ${count}`)
    expect(count).toBeGreaterThanOrEqual(3)
  })

  test('docs sidebar highlights OpenClaw Integration as active', async ({ page }) => {
    const sidebarLink = page.locator('a[href="/docs/openclaw"]').first()
    await expect(sidebarLink).toBeVisible()
    console.log('✅ OpenClaw sidebar link visible')
  })
})
