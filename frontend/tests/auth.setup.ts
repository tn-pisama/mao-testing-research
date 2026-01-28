import { test as setup, expect } from '@playwright/test'
import path from 'path'

const authFile = path.join(__dirname, 'auth/storage-state.json')

/**
 * Authentication setup for E2E tests
 *
 * This test must be run manually with --headed flag:
 *   npx playwright test auth.setup.ts --headed
 *
 * You'll have 90 seconds to complete Google OAuth login.
 * After successful login, your session will be saved and reused by authenticated tests.
 */
setup('authenticate via Google OAuth', async ({ page }) => {
  console.log('🔐 Starting authentication setup...')
  console.log('ℹ️  You will need to manually complete Google OAuth')

  // Navigate to sign in page
  await page.goto('/sign-in')
  console.log('📝 Navigated to /sign-in')

  // Wait for user to complete OAuth flow
  console.log('⏳ Please complete Google OAuth sign-in...')
  console.log('   You have 90 seconds to sign in.')

  // Wait for redirect to dashboard (indicates successful login)
  try {
    await page.waitForURL('**/dashboard', { timeout: 90000 })
    console.log('✅ Successfully signed in!')
  } catch (error) {
    console.error('❌ Timeout: Sign-in not completed within 90 seconds')
    throw error
  }

  // Verify we're actually logged in
  await expect(page).toHaveURL(/dashboard/)

  // Save authenticated state
  await page.context().storageState({ path: authFile })
  console.log('💾 Auth state saved to:', authFile)
  console.log('✨ Setup complete! Authenticated tests can now run.')
})
