import { SignIn } from '@clerk/nextjs'
import { auth } from '@clerk/nextjs/server'
import { redirect } from 'next/navigation'

export default async function Home() {
  const { userId } = await auth()
  
  if (userId) {
    redirect('/dashboard')
  }

  return (
    <main className="min-h-screen bg-slate-900">
      <div className="max-w-7xl mx-auto px-4 py-16 sm:px-6 lg:px-8">
        <div className="grid lg:grid-cols-2 gap-16 items-center">
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
                <div className="w-6 h-6 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <div>
                  <h3 className="text-white font-medium">Real-time Detection</h3>
                  <p className="text-slate-400 text-sm">Catch loops, drift, and corruption as they happen</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="w-6 h-6 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <div>
                  <h3 className="text-white font-medium">Multi-Framework Support</h3>
                  <p className="text-slate-400 text-sm">LangGraph, CrewAI, AutoGen, n8n, and more</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="w-6 h-6 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <div>
                  <h3 className="text-white font-medium">AI-Powered Fixes</h3>
                  <p className="text-slate-400 text-sm">Get actionable fix suggestions for every detection</p>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-4 text-sm text-slate-400">
              <span>Trusted by teams building production AI agents</span>
            </div>
          </div>
          <div className="flex justify-center lg:justify-end">
            <SignIn afterSignInUrl="/dashboard" />
          </div>
        </div>
      </div>
    </main>
  )
}
