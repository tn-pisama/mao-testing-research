import { test, expect } from '@playwright/test'

const API_BASE = process.env.TEST_API_URL || 'https://mao-api.fly.dev'

test.describe('Backend Health Check', () => {
  test('health endpoint returns 200 with healthy status', async ({ request }) => {
    const response = await request.get(`${API_BASE}/health`)

    expect(response.status()).toBe(200)

    const body = await response.json()
    expect(body).toHaveProperty('status')
    expect(body.status).toMatch(/healthy|degraded/)

    console.log('✅ Health check:', body)
  })

  test('health endpoint responds within acceptable latency', async ({ request }) => {
    const start = Date.now()
    const response = await request.get(`${API_BASE}/health`)
    const latency = Date.now() - start

    expect(response.status()).toBe(200)
    expect(latency).toBeLessThan(3000) // 3 second max

    console.log(`⏱️  Health check latency: ${latency}ms`)
  })

  test('API base URL is reachable', async ({ request }) => {
    // Test that we can at least get a response from the API
    const response = await request.get(`${API_BASE}/health`)

    // Should not timeout or fail to connect
    expect(response.ok()).toBeTruthy()
  })
})
