import { test, expect } from '@playwright/test'

test.describe('Clerk Authentication', () => {
  test('homepage shows Sign In and Sign Up buttons when not authenticated', async ({ page }) => {
    await page.goto('http://localhost:3002')
    
    await expect(page.getByRole('button', { name: 'Sign In' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Sign Up' })).toBeVisible()
  })

  test('Sign In button opens Clerk modal', async ({ page }) => {
    await page.goto('http://localhost:3002')
    
    await page.getByRole('button', { name: 'Sign In' }).click()
    
    // Wait for Clerk modal to appear
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 10000 })
    await expect(page.getByText('Sign in to MAO')).toBeVisible()
  })

  test('Sign Up button opens Clerk modal', async ({ page }) => {
    await page.goto('http://localhost:3002')
    
    await page.getByRole('button', { name: 'Sign Up' }).click()
    
    // Wait for Clerk modal to appear
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 10000 })
    await expect(page.getByText('Create your account')).toBeVisible()
  })
})
