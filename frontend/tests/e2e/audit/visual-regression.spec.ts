import { test, expect } from '@playwright/test'

test.setTimeout(60000)

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
      await page.goto(pg.path, { waitUntil: 'domcontentloaded' })
      await page.waitForTimeout(3000)

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
      await page.goto(pg.path, { waitUntil: 'domcontentloaded' })
      await page.waitForTimeout(3000)

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

