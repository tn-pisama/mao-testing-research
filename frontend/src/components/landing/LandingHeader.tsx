'use client'

import { Search } from 'lucide-react'

interface LandingHeaderProps {
  onJoinWaitlist: () => void
}

export function LandingHeader({ onJoinWaitlist }: LandingHeaderProps) {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-slate-900/80 backdrop-blur-md border-b border-slate-800">
      <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2">
          <Search className="w-6 h-6 text-primary-500" />
          <span className="text-xl font-black text-white tracking-tight">PISAMA</span>
        </Link>

        {/* Navigation */}
        <nav className="hidden md:flex items-center gap-6">
          <a
            href="https://pypi.org/project/pisama-claude-code/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-slate-400 hover:text-white transition-colors text-sm"
          >
            PyPI
          </a>
          <a
            href="https://github.com/tn-pisama/pisama-claude-code"
            target="_blank"
            rel="noopener noreferrer"
            className="text-slate-400 hover:text-white transition-colors text-sm"
          >
            GitHub
          </a>
          <a
            href="https://github.com/tn-pisama/pisama-claude-code#readme"
            target="_blank"
            rel="noopener noreferrer"
            className="text-slate-400 hover:text-white transition-colors text-sm"
          >
            Docs
          </a>
        </nav>

        {/* Auth Buttons */}
        <div className="flex items-center gap-3">
          <a
            href="/sign-in"
            className="text-slate-300 hover:text-white transition-colors text-sm px-3 py-2"
          >
            Sign In
          </a>
          <button
            onClick={onJoinWaitlist}
            className="bg-primary-600 hover:bg-primary-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            Join Waitlist
          </button>
        </div>
      </div>
    </header>
  )
}
