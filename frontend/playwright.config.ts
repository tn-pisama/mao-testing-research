import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright configuration for frontend-backend connection verification
 * Tests production deployment at https://pisama.ai
 */
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,

  reporter: [
    ['html', { open: 'never' }],
    ['list'],
  ],

  use: {
    // Production URLs
    baseURL: process.env.TEST_BASE_URL || 'https://pisama.ai',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  projects: [
    // API-only tests (no browser needed)
    {
      name: 'api',
      testMatch: /.*\/api\/.*\.spec\.ts/,
      use: {
        // Direct HTTP requests, no browser
      },
    },

    // Public page tests (no auth required)
    {
      name: 'public',
      testMatch: /.*\/public\/.*\.spec\.ts/,
      use: { ...devices['Desktop Chrome'] },
    },

    // Setup project for authentication
    {
      name: 'auth-setup',
      testMatch: /auth\.setup\.ts/,
      use: { ...devices['Desktop Chrome'] },
    },

    // Authenticated tests (requires auth setup first)
    {
      name: 'authenticated',
      testMatch: /.*\/authenticated\/.*\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        storageState: './tests/auth/storage-state.json',
      },
      dependencies: ['auth-setup'],
    },
  ],

  // Global timeout for individual tests
  timeout: 30000,

  // Timeout for assertions
  expect: {
    timeout: 10000,
  },
})
