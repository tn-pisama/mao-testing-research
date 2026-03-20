'use client'

import { useState } from 'react'
import { X } from 'lucide-react'
import { Button } from '../ui/Button'

interface WaitlistModalProps {
  isOpen: boolean
  onClose: () => void
}

export function WaitlistModal({ isOpen, onClose }: WaitlistModalProps) {
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle')

  if (!isOpen) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email || !email.includes('@')) return

    setStatus('sending')
    try {
      await fetch('/api/waitlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      })
      setStatus('sent')
      setEmail('')
      setTimeout(() => {
        onClose()
        setStatus('idle')
      }, 2000)
    } catch {
      setStatus('error')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div
        className="relative bg-zinc-900 rounded-xl border border-zinc-700 p-8 max-w-md w-full mx-4"
        role="dialog"
        aria-modal="true"
      >
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-zinc-400 hover:text-white transition-colors"
          aria-label="Close"
        >
          <X size={20} />
        </button>

        <h2 className="text-xl font-bold text-white mb-2">Join the Waitlist</h2>
        <p className="text-zinc-400 text-sm mb-6">
          Get early access to Pisama when we launch.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
            disabled={status === 'sending' || status === 'sent'}
            className="w-full px-4 py-3 rounded-lg bg-zinc-800 border border-zinc-700 text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50"
          />

          {status === 'error' && (
            <p className="text-sm text-red-400">Something went wrong. Please try again.</p>
          )}

          {status === 'sent' ? (
            <p className="text-sm text-green-400">Thanks! We will be in touch.</p>
          ) : (
            <Button
              type="submit"
              className="w-full"
              disabled={status === 'sending'}
            >
              {status === 'sending' ? 'Joining...' : 'Join Waitlist'}
            </Button>
          )}
        </form>
      </div>
    </div>
  )
}
