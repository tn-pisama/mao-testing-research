'use client'

import Link from 'next/link'
import { SignIn, SignedIn, SignedOut } from '@clerk/nextjs'

function AuthPlaceholder() {
  return (
    <div className="bg-slate-800 rounded-lg p-8 w-[400px] h-[400px] flex items-center justify-center">
      <div className="animate-pulse text-slate-400">Loading...</div>
    </div>
  )
}

function CheckIcon() {
  return (
    <div className="w-6 h-6 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0 mt-0.5">
      <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
      </svg>
    </div>
  )
}

function LandingContent() {
  return (
    <div>
      <h1 className="text-4xl sm:text-5xl font-bold text-white mb-6">
        Catch AI Agent Failures
        <span className="text-blue-500"> Before They Cost You</span>
      </h1>
      <p className="text-xl text-slate-300 mb-8">
        MAO Testing Platform automatically detects infinite loops, state corruption, 
        persona drift, and coordination failures in your LLM agent systems.
      </p>
      <div className="space-y-4 mb-8">
        <div className="flex items-start gap-3">
          <CheckIcon />
          <div>
            <h3 className="text-white font-medium">Real-time Detection</h3>
            <p className="text-slate-400 text-sm">Catch loops, drift, and corruption as they happen</p>
          </div>
        </div>
        <div className="flex items-start gap-3">
          <CheckIcon />
          <div>
            <h3 className="text-white font-medium">Multi-Framework Support</h3>
            <p className="text-slate-400 text-sm">LangGraph, CrewAI, AutoGen, n8n, and more</p>
          </div>
        </div>
        <div className="flex items-start gap-3">
          <CheckIcon />
          <div>
            <h3 className="text-white font-medium">AI-Powered Fixes</h3>
            <p className="text-slate-400 text-sm">Get actionable fix suggestions for every detection</p>
          </div>
        </div>
      </div>
      <p className="text-sm text-slate-400">
        Trusted by teams building production AI agents
      </p>
    </div>
  )
}

function AuthSection() {
  return (
    <>
      <SignedOut>
        <SignIn afterSignInUrl="/dashboard" routing="hash" />
      </SignedOut>
      <SignedIn>
        <div className="bg-slate-800 rounded-lg p-8 text-center">
          <h2 className="text-xl font-semibold text-white mb-4">Welcome back!</h2>
          <p className="text-slate-400 mb-6">You are already signed in.</p>
          <Link 
            href="/dashboard" 
            className="inline-block bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg transition-colors font-medium"
          >
            Go to Dashboard
          </Link>
        </div>
      </SignedIn>
    </>
  )
}

export default function Home() {
  return (
    <main className="min-h-screen bg-slate-900">
      <div className="max-w-7xl mx-auto px-4 py-16 sm:px-6 lg:px-8">
        <div className="grid lg:grid-cols-2 gap-16 items-center min-h-[80vh]">
          <LandingContent />
          <div className="flex justify-center lg:justify-end">
            <AuthSection />
          </div>
        </div>
      </div>
    </main>
  )
}
