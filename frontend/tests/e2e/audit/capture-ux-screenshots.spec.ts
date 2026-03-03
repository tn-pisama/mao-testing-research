import { test } from '@playwright/test'
import { join } from 'path'

const SCREENSHOTS_DIR = join(process.cwd(), 'test-results', 'ux-review')

const pages = [
  { path: '/dashboard', name: 'Dashboard' },
  { path: '/dify', name: 'Dify' },
  { path: '/openclaw', name: 'OpenClaw' },
  { path: '/langgraph', name: 'LangGraph' },
  { path: '/integrations', name: 'Integrations' },
  { path: '/docs/getting-started', name: 'Docs-GettingStarted' },
  { path: '/docs/dify', name: 'Docs-Dify' },
  { path: '/docs/openclaw', name: 'Docs-OpenClaw' },
  { path: '/docs/langgraph', name: 'Docs-LangGraph' },
]

test.describe('UX Screenshot Capture', () => {
  for (const pg of pages) {
    test(`capture ${pg.name}`, async ({ page }) => {
      await page.goto(pg.path)
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(2000)

      await page.screenshot({
        path: join(SCREENSHOTS_DIR, `${pg.name}.png`),
        fullPage: true,
      })
      console.log(`📸 ${pg.name} captured`)
    })
  }

  // Capture interactive states
  test('capture Dify with modal open', async ({ page }) => {
    await page.goto('/dify')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    await page.getByRole('button', { name: /Add Instance/i }).click()
    await page.waitForTimeout(500)
    await page.screenshot({
      path: join(SCREENSHOTS_DIR, 'Dify-modal.png'),
      fullPage: false,
    })
    console.log('📸 Dify modal captured')
  })

  test('capture Integrations tabs', async ({ page }) => {
    await page.goto('/integrations')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    for (const tab of ['n8n', 'Dify', 'OpenClaw', 'LangGraph']) {
      await page.locator('button').filter({ hasText: tab }).first().click()
      await page.waitForTimeout(500)
      await page.screenshot({
        path: join(SCREENSHOTS_DIR, `Integrations-${tab}.png`),
        fullPage: false,
      })
    }
    console.log('📸 Integration tabs captured')
  })
})
