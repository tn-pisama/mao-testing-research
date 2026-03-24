/**
 * Single source of truth for the backend API URL.
 *
 * HARDCODED for production — no env var dependency.
 * This eliminates Vercel build cache issues, env var encoding (\n),
 * and http:// vs https:// mismatches that plagued NEXT_PUBLIC_API_URL.
 *
 * For local development: uses NEXT_PUBLIC_API_URL from .env.local
 */
const API_URL = process.env.NODE_ENV === 'development'
  ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1')
  : 'https://mao-api.fly.dev/api/v1'

export default API_URL
