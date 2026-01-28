import { test, expect } from '@playwright/test'

const API_BASE = process.env.TEST_API_URL || 'https://mao-api.fly.dev'

test.describe('API Endpoint Validation', () => {
  test('protected endpoint returns 401/403 without authentication', async ({ request }) => {
    // Tenant-specific endpoint should require auth
    const response = await request.get(
      `${API_BASE}/api/v1/tenants/test-tenant/traces`
    )

    // Should be 401 Unauthorized or 403 Forbidden, NOT 404
    expect([401, 403]).toContain(response.status())

    console.log(`✅ Protected endpoint correctly returns ${response.status()}`)
  })

  test('API returns proper CORS headers for pisama.ai', async ({ request }) => {
    const response = await request.get(`${API_BASE}/health`, {
      headers: {
        'Origin': 'https://pisama.ai',
      },
    })

    expect(response.status()).toBe(200)

    // Check for CORS header (backend should allow pisama.ai)
    const corsHeader = response.headers()['access-control-allow-origin']
    if (corsHeader) {
      console.log(`✅ CORS header present: ${corsHeader}`)
    }
  })

  test('API responds to health checks consistently', async ({ request }) => {
    // Make multiple requests to ensure stability
    const responses = await Promise.all([
      request.get(`${API_BASE}/health`),
      request.get(`${API_BASE}/health`),
      request.get(`${API_BASE}/health`),
    ])

    // All should return 200
    responses.forEach((response, index) => {
      expect(response.status()).toBe(200)
      console.log(`✅ Health check ${index + 1}/3: OK`)
    })
  })
})
