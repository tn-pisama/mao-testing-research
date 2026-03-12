'use client'

import { useState } from 'react'
import { X } from 'lucide-react'
import { Button } from '../ui/Button'
import { analytics } from '@/lib/analytics'

interface WaitlistModalProps {
  isOpen: boolean
  onClose: () => void
}

export function WaitlistModal({ isOpen, onClose }: WaitlistModalProps) {
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState('')

  if (!isOpen) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!email || !email.includes('@')) {
      setStatus('error')
      setMessage('Please enter a valid email address')
      return
    }

    setStatus('loading')
    setMessage('')

    try {
      const response = await fetch('/api/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      })

      const data = await response.json()

      if (response.ok) {
        setStatus('success')
        setMessage(data.message || 'Thanks for signing up!')
        setEmail('')

        // Track successful signup
        analytics.waitlistSignup('modal')
        analytics.emailSubmit('success', 'modal')

        // Auto-close after 2 seconds on success
        setTimeout(() => {
          onClose()
          setStatus('idle')
          setMessage('')
        }, 2000)
      } else {
        setStatus('error')
        setMessage(data.error || 'Something went wrong. Please try again.')
        analytics.emailSubmit('error', 'modal')
      }
    } catch {
      setStatus('error')
      setMessage('Network error. Please try again.')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative bg-zinc-900 rounded-xl border border-zinc-700 p-8 max-w-md w-full mx-4">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-zinc-400 hover:text-white transition-colors"
          aria-label="Close dialog"
        >
          <X size={20} />
        </button>

        <h2 className="text-2xl font-bold text-white mb-2">
          Get Early Access
        </h2>
        <p className="text-zinc-400 mb-6">
          Join the waitlist and be first to test PISAMA when we launch Q1 2026.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-zinc-300 mb-2">
              Email Address
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="your@email.com"
              disabled={status === 'loading' || status === 'success'}
              className="w-full px-4 py-3 rounded-lg bg-zinc-800 border border-zinc-700 text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed"
            />
          </div>

          {message && (
            <div
              className={`text-sm ${
                status === 'success' ? 'text-green-400' : 'text-red-400'
              }`}
            >
              {message}
            </div>
          )}

          <Button
            type="submit"
            disabled={status === 'loading' || status === 'success'}
            className="w-full"
          >
            {status === 'loading' ? 'Joining...' : status === 'success' ? 'Joined!' : 'Join Waitlist'}
          </Button>
        </form>

        <p className="text-xs text-zinc-500 mt-4 text-center">
          We&apos;ll send you launch updates and early access when ready. No spam, ever.
        </p>
      </div>
    </div>
  )
}
