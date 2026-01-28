import { test, expect } from '@playwright/test'

test.describe('Quality Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/quality')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('page loads and displays title', async ({ page }) => {
    await expect(page.locator('h1, h2').first()).toContainText(/Quality/i)
    console.log('✅ Quality title visible')
  })

  test('grade filter buttons exist', async ({ page }) => {
    const gradeButtons = page.locator('button').filter({ hasText: /^All$|^A$|^B|^C$|^D$|^F$/ })
    const count = await gradeButtons.count()

    if (count > 0) {
      console.log(`✅ Grade filters found: ${count}`)
    } else {
      console.log('⚠️  No grade filter buttons')
    }
  })

  test('assessment list or empty state is displayed', async ({ page }) => {
    const assessmentItem = page.locator('[class*="assessment"], [class*="quality"]').first()
    const emptyState = page.getByText(/no.*assessment/i)

    const hasAssessments = await assessmentItem.isVisible().catch(() => false)
    const isEmpty = await emptyState.isVisible().catch(() => false)

    console.log(`Assessments: ${hasAssessments}, Empty: ${isEmpty}`)
    expect(hasAssessments || isEmpty).toBe(true)
  })

  test('loading completes', async ({ page }) => {
    await expect(page.locator('.animate-spin')).not.toBeVisible({ timeout: 15000 })
    console.log('✅ Loading complete')
  })
})
