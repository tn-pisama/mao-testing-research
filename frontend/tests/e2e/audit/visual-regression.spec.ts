import { test, expect } from '@playwright/test'

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

test.describe('Visual Regression - Full Page Baselines', () => {
  for (const pg of pages) {
    test(`${pg.name} matches visual baseline`, async ({ page }) => {
      await page.goto(pg.path)
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(2000)

      // Hide any animated elements that cause flaky diffs
      await page.evaluate(() => {
        document.querySelectorAll('.animate-spin, .animate-pulse, .animate-bounce').forEach(el => {
          ;(el as HTMLElement).style.display = 'none'
        })
      })

      await expect(page).toHaveScreenshot(`${pg.name}-full.png`, {
        fullPage: true,
        maxDiffPixelRatio: 0.02,
        timeout: 15000,
      })
      console.log(`✅ ${pg.name} baseline captured/matched`)
    })
  }
})

test.describe('Visual Regression - Above-the-Fold', () => {
  for (const pg of pages) {
    test(`${pg.name} above-the-fold matches baseline`, async ({ page }) => {
      await page.goto(pg.path)
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(2000)

      await page.evaluate(() => {
        document.querySelectorAll('.animate-spin, .animate-pulse, .animate-bounce').forEach(el => {
          ;(el as HTMLElement).style.display = 'none'
        })
      })

      await expect(page).toHaveScreenshot(`${pg.name}-viewport.png`, {
        fullPage: false,
        maxDiffPixelRatio: 0.02,
        timeout: 15000,
      })
      console.log(`✅ ${pg.name} viewport baseline captured/matched`)
    })
  }
})

test.describe('Visual Regression - Interactive States', () => {
  test('Dify modal open state', async ({ page }) => {
    await page.goto('/dify')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    await page.getByRole('button', { name: /Add Instance/i }).click()
    await page.waitForTimeout(500)

    await expect(page).toHaveScreenshot('Dify-modal-open.png', {
      maxDiffPixelRatio: 0.02,
    })
    console.log('✅ Dify modal state captured')
  })

  test('Integrations tab states', async ({ page }) => {
    await page.goto('/integrations')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // Capture each tab state
    const tabs = ['n8n', 'Dify', 'OpenClaw', 'LangGraph']
    for (const tab of tabs) {
      await page.locator('button').filter({ hasText: tab }).first().click()
      await page.waitForTimeout(500)

      await page.evaluate(() => {
        document.querySelectorAll('.animate-spin, .animate-pulse').forEach(el => {
          ;(el as HTMLElement).style.display = 'none'
        })
      })

      await expect(page).toHaveScreenshot(`Integrations-tab-${tab}.png`, {
        maxDiffPixelRatio: 0.02,
      })
    }
    console.log('✅ All integration tab states captured')
  })
})
