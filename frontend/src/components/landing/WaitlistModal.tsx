'use client'

import { useState } from 'react'
import { X, CheckCircle, Loader2 } from 'lucide-react'

interface WaitlistModalProps {
  isOpen: boolean
  onClose: () => void
}

export function WaitlistModal({ isOpen, onClose }: WaitlistModalProps) {
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [errorMessage, setErrorMessage] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!email || !email.includes('@')) {
      setErrorMessage('Please enter a valid email address')
      setStatus('error')
      return
    }

    setStatus('loading')

    // For now, just simulate a successful submission
    // In production, this would call an API endpoint
    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000))

      // Store in localStorage as a simple solution
      const waitlist = JSON.parse(localStorage.getItem('pisama_waitlist') || '[]')
      if (!waitlist.includes(email)) {
        waitlist.push(email)
        localStorage.setItem('pisama_waitlist', JSON.stringify(waitlist))
      }

      setStatus('success')
    } catch {
      setErrorMessage('Something went wrong. Please try again.')
      setStatus('error')
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-slate-800 border border-slate-700 rounded-2xl p-8 max-w-md w-full shadow-2xl">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-white transition-colors"
        >
          <X size={20} />
        </button>

        {status === 'success' ? (
          <div className="text-center py-4">
            <CheckCircle className="w-16 h-16 text-emerald-400 mx-auto mb-4" />
            <h3 className="text-xl font-bold text-white mb-2">
              You&apos;re on the list!
            </h3>
            <p className="text-slate-400 mb-6">
              We&apos;ll notify you when the PISAMA platform launches.
            </p>
            <button
              onClick={onClose}
              className="text-primary-400 hover:text-primary-300 font-medium"
            >
              Close
            </button>
          </div>
        ) : (
          <>
            <h3 className="text-xl font-bold text-white mb-2">
              Join the Waitlist
            </h3>
            <p className="text-slate-400 mb-6">
              Get early access to the PISAMA platform with advanced failure detection
              and self-healing capabilities.
            </p>

            <form onSubmit={handleSubmit}>
              <div className="mb-4">
                <label htmlFor="email" className="block text-sm font-medium text-slate-300 mb-2">
                  Email address
                </label>
                <input
                  type="email"
                  id="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value)
                    setStatus('idle')
                    setErrorMessage('')
                  }}
                  placeholder="you@example.com"
                  className="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-primary-500 transition-colors"
                />
                {status === 'error' && (
                  <p className="text-red-400 text-sm mt-2">{errorMessage}</p>
                )}
              </div>

              <button
                type="submit"
                disabled={status === 'loading'}
                className="w-full bg-primary-600 hover:bg-primary-500 disabled:bg-primary-600/50 text-white font-medium py-3 rounded-lg transition-colors flex items-center justify-center gap-2"
              >
                {status === 'loading' ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Joining...
                  </>
                ) : (
                  'Join Waitlist'
                )}
              </button>
            </form>

            <p className="text-slate-500 text-xs mt-4 text-center">
              We respect your privacy. No spam, ever.
            </p>
          </>
        )}
      </div>
    </div>
  )
}
