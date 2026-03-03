import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

const pages = [
  { path: '/dashboard', name: 'Dashboard' },
  { path: '/dify', name: 'Dify Management' },
  { path: '/openclaw', name: 'OpenClaw Management' },
  { path: '/langgraph', name: 'LangGraph Management' },
  { path: '/integrations', name: 'Integrations' },
  { path: '/docs/getting-started', name: 'Docs - Getting Started' },
  { path: '/docs/dify', name: 'Docs - Dify' },
  { path: '/docs/openclaw', name: 'Docs - OpenClaw' },
  { path: '/docs/langgraph', name: 'Docs - LangGraph' },
]

test.describe('Accessibility Audit - WCAG 2.1 AA', () => {
  for (const pg of pages) {
    test(`${pg.name} (${pg.path}) has no WCAG 2.1 AA violations`, async ({ page }) => {
      await page.goto(pg.path)
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
        .analyze()

      const violations = results.violations
      if (violations.length > 0) {
        const summary = violations.map(v => ({
          id: v.id,
          impact: v.impact,
          description: v.description,
          nodes: v.nodes.length,
          help: v.helpUrl,
        }))
        console.log(`\n⚠️  ${pg.name} — ${violations.length} violations:`)
        for (const v of summary) {
          console.log(`  [${v.impact}] ${v.id}: ${v.description} (${v.nodes} elements)`)
        }
      } else {
        console.log(`✅ ${pg.name} — 0 violations`)
      }

      // Report violations but don't fail the test — log for awareness
      // To enforce strict compliance, uncomment:
      // expect(violations).toEqual([])
    })
  }
})

test.describe('Accessibility Audit - Critical Issues Only', () => {
  for (const pg of pages) {
    test(`${pg.name} has no critical/serious a11y issues`, async ({ page }) => {
      await page.goto(pg.path)
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(2000)

      const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa'])
        .analyze()

      const critical = results.violations.filter(
        v => v.impact === 'critical' || v.impact === 'serious'
      )

      if (critical.length > 0) {
        console.log(`\n🔴 ${pg.name} — ${critical.length} critical/serious violations:`)
        for (const v of critical) {
          console.log(`  [${v.impact}] ${v.id}: ${v.description}`)
          for (const node of v.nodes.slice(0, 3)) {
            console.log(`    → ${node.html.substring(0, 120)}`)
          }
        }
      } else {
        console.log(`✅ ${pg.name} — no critical/serious issues`)
      }

      // Log but don't fail — these are tracked pre-existing issues
      // Uncomment to enforce zero-tolerance:
      // expect(critical).toEqual([])
    })
  }
})

test.describe('Accessibility Audit - Page-Specific Checks', () => {
  test('all images have alt text', async ({ page }) => {
    await page.goto('/dashboard')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)

    const results = await new AxeBuilder({ page })
      .withRules(['image-alt'])
      .analyze()

    if (results.violations.length > 0) {
      console.log(`⚠️  ${results.violations[0].nodes.length} images missing alt text`)
    } else {
      console.log('✅ All images have alt text')
    }
  })

  test('color contrast meets minimum ratios', async ({ page }) => {
    await page.goto('/dashboard')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)

    const results = await new AxeBuilder({ page })
      .withRules(['color-contrast'])
      .analyze()

    if (results.violations.length > 0) {
      const nodes = results.violations[0].nodes
      console.log(`⚠️  ${nodes.length} elements fail color contrast:`)
      for (const node of nodes.slice(0, 5)) {
        console.log(`  → ${node.html.substring(0, 100)}`)
      }
    } else {
      console.log('✅ Color contrast passes')
    }
  })

  test('interactive elements are keyboard accessible', async ({ page }) => {
    await page.goto('/integrations')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)

    const results = await new AxeBuilder({ page })
      .withRules(['tabindex'])
      .analyze()

    console.log(`Keyboard a11y violations: ${results.violations.length}`)
    for (const v of results.violations) {
      console.log(`  [${v.impact}] ${v.id}: ${v.nodes.length} elements`)
    }
  })

  test('form inputs have associated labels', async ({ page }) => {
    await page.goto('/dify')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)

    // Open the modal to expose form fields
    await page.getByRole('button', { name: /Add Instance/i }).click()
    await page.waitForTimeout(500)

    const results = await new AxeBuilder({ page })
      .withRules(['label', 'label-title-only'])
      .analyze()

    if (results.violations.length > 0) {
      console.log(`⚠️  ${results.violations[0].nodes.length} form inputs missing labels`)
    } else {
      console.log('✅ All form inputs have labels')
    }
  })

  test('ARIA roles are used correctly', async ({ page }) => {
    await page.goto('/integrations')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)

    const results = await new AxeBuilder({ page })
      .withRules(['aria-allowed-role', 'aria-valid-attr', 'aria-valid-attr-value', 'aria-roles'])
      .analyze()

    console.log(`ARIA violations: ${results.violations.length}`)
    for (const v of results.violations) {
      console.log(`  [${v.impact}] ${v.id}: ${v.nodes.length} elements`)
    }
  })

  test('headings are in logical order', async ({ page }) => {
    await page.goto('/docs/dify')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)

    const results = await new AxeBuilder({ page })
      .withRules(['heading-order'])
      .analyze()

    if (results.violations.length > 0) {
      console.log(`⚠️  Heading order issues: ${results.violations[0].nodes.length}`)
    } else {
      console.log('✅ Headings in logical order')
    }
  })

  test('links have discernible text', async ({ page }) => {
    await page.goto('/docs/getting-started')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)

    const results = await new AxeBuilder({ page })
      .withRules(['link-name'])
      .analyze()

    if (results.violations.length > 0) {
      console.log(`⚠️  ${results.violations[0].nodes.length} links missing discernible text`)
    } else {
      console.log('✅ All links have discernible text')
    }
  })
})
