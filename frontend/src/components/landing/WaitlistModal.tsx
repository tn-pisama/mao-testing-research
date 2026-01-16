'use client'

import { X } from 'lucide-react'
import { Button } from '../ui/Button'

interface WaitlistModalProps {
  isOpen: boolean
  onClose: () => void
}

export function WaitlistModal({ isOpen, onClose }: WaitlistModalProps) {
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative bg-slate-900 rounded-xl border border-slate-700 p-6 max-w-md w-full mx-4">
        <button onClick={onClose} className="absolute top-4 right-4 text-slate-400 hover:text-white">
          <X size={20} />
        </button>
        <h2 className="text-xl font-bold text-white mb-4">Join Waitlist</h2>
        <p className="text-slate-400 mb-4">Coming soon</p>
        <Button onClick={onClose}>Close</Button>
      </div>
    </div>
  )
}
