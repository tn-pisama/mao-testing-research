import { SignUp } from '@clerk/nextjs'
import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'

export default function SignUpPage() {
  return (
    <main className="min-h-screen bg-zinc-900 flex flex-col items-center justify-center p-4">
      <Link
        href="/"
        className="absolute top-6 left-6 flex items-center gap-2 text-zinc-400 hover:text-white transition-colors"
      >
        <ArrowLeft size={16} />
        <span>Back</span>
      </Link>

      <SignUp
        appearance={{
          elements: {
            rootBox: 'mx-auto',
            card: 'bg-zinc-800 border border-zinc-700 shadow-xl',
            headerTitle: 'text-white',
            headerSubtitle: 'text-zinc-400',
            socialButtonsBlockButton: 'bg-zinc-700 border-zinc-600 text-white hover:bg-zinc-600',
            formFieldLabel: 'text-zinc-300',
            formFieldInput: 'bg-zinc-700 border-zinc-600 text-white',
            footerActionLink: 'text-blue-400 hover:text-blue-300',
            formButtonPrimary: 'bg-blue-600 hover:bg-blue-500',
          },
        }}
        fallbackRedirectUrl="/dashboard"
      />
    </main>
  )
}
