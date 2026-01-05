import { SignUp } from '@clerk/nextjs'
import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'

export default function SignUpPage() {
  return (
    <main className="min-h-screen bg-slate-900 flex flex-col items-center justify-center p-4">
      <Link
        href="/"
        className="absolute top-6 left-6 flex items-center gap-2 text-slate-400 hover:text-white transition-colors"
      >
        <ArrowLeft size={16} />
        <span>Back</span>
      </Link>

      <SignUp
        appearance={{
          elements: {
            rootBox: 'mx-auto',
            card: 'bg-slate-800 border border-slate-700 shadow-xl',
            headerTitle: 'text-white',
            headerSubtitle: 'text-slate-400',
            socialButtonsBlockButton: 'bg-slate-700 border-slate-600 text-white hover:bg-slate-600',
            formFieldLabel: 'text-slate-300',
            formFieldInput: 'bg-slate-700 border-slate-600 text-white',
            footerActionLink: 'text-primary-400 hover:text-primary-300',
            formButtonPrimary: 'bg-primary-600 hover:bg-primary-500',
          },
        }}
        fallbackRedirectUrl="/dashboard"
      />
    </main>
  )
}
