'use client'

import Link from 'next/link'
import { Search } from 'lucide-react'

export function Footer() {
  return (
    <footer className="border-t border-slate-800 py-12 px-6">
      <div className="max-w-6xl mx-auto">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          {/* Logo */}
          <div className="flex items-center gap-2">
            <Search className="w-5 h-5 text-primary-500" />
            <span className="text-lg font-bold text-white">PISAMA</span>
          </div>

          {/* Links */}
          <div className="flex items-center gap-6 text-sm">
            <a
              href="https://pypi.org/project/pisama-claude-code/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-400 hover:text-white transition-colors"
            >
              PyPI
            </a>
            <a
              href="https://github.com/tn-pisama/pisama-claude-code"
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-400 hover:text-white transition-colors"
            >
              GitHub
            </a>
            <a
              href="https://github.com/tn-pisama/pisama-claude-code#readme"
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-400 hover:text-white transition-colors"
            >
              Documentation
            </a>
            <Link
              href="/terms"
              className="text-slate-400 hover:text-white transition-colors"
            >
              Terms
            </Link>
          </div>

          {/* Copyright */}
          <p className="text-slate-500 text-sm">
            {new Date().getFullYear()} PISAMA. MIT License.
          </p>
        </div>
      </div>
    </footer>
  )
}
