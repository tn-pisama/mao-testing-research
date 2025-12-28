import { SignIn } from '@clerk/nextjs'
import { auth } from '@clerk/nextjs/server'
import { redirect } from 'next/navigation'

export default async function Home() {
  const { userId } = await auth()
  
  if (userId) {
    redirect('/dashboard')
  }

  return (
    <main className="min-h-screen bg-slate-900 flex items-center justify-center">
      <SignIn afterSignInUrl="/dashboard" />
    </main>
  )
}
