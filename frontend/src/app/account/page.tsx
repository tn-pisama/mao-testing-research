'use client'

import { Layout } from '@/components/common/Layout'
import { useSafeAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import { User, Mail, Building2, LogOut, CreditCard } from 'lucide-react'
import { useSession, signOut } from 'next-auth/react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'

export default function AccountPage() {
  const { isSignedIn } = useSafeAuth()
  const { tenantId } = useTenant()
  const { data: session } = useSession()
  const router = useRouter()

  const handleSignOut = async () => {
    await signOut({ callbackUrl: '/' })
  }

  if (!isSignedIn || !session?.user) {
    return (
      <Layout>
        <div className="p-6">
          <p className="text-slate-400">Please sign in to view your account.</p>
        </div>
      </Layout>
    )
  }

  const user = session.user

  return (
    <Layout>
      <div className="p-6 max-w-4xl mx-auto">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white mb-2">Account Settings</h1>
          <p className="text-slate-400">Manage your profile and account preferences</p>
        </div>

        {/* User Profile Section */}
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-6 mb-6">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <User size={20} />
            Profile Information
          </h2>

          <div className="space-y-4">
            {/* Profile Image */}
            {user.image && (
              <div className="flex items-center gap-4">
                <img
                  src={user.image}
                  alt={user.name || 'User'}
                  className="w-16 h-16 rounded-full border-2 border-slate-600"
                />
                <div>
                  <p className="text-sm text-slate-400">Profile Picture</p>
                  <p className="text-white font-medium">{user.name || 'Not set'}</p>
                </div>
              </div>
            )}

            {/* Name */}
            <div className="flex items-start gap-3 py-3 border-t border-slate-700">
              <User size={18} className="text-slate-400 mt-0.5" />
              <div className="flex-1">
                <p className="text-sm text-slate-400">Full Name</p>
                <p className="text-white">{user.name || 'Not set'}</p>
              </div>
            </div>

            {/* Email */}
            <div className="flex items-start gap-3 py-3 border-t border-slate-700">
              <Mail size={18} className="text-slate-400 mt-0.5" />
              <div className="flex-1">
                <p className="text-sm text-slate-400">Email Address</p>
                <p className="text-white">{user.email}</p>
              </div>
            </div>

            {/* Tenant/Organization */}
            {tenantId && tenantId !== 'default' && (
              <div className="flex items-start gap-3 py-3 border-t border-slate-700">
                <Building2 size={18} className="text-slate-400 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm text-slate-400">Organization</p>
                  <p className="text-white">{tenantId}</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Billing Section */}
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-6 mb-6">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <CreditCard size={20} />
            Billing
          </h2>
          <p className="text-slate-400 mb-4">
            Manage your subscription and billing information.
          </p>
          <Link
            href="/billing"
            className="inline-flex items-center gap-2 px-4 py-2 bg-sky-500 text-white rounded-lg hover:bg-sky-600 transition-colors"
          >
            Go to Billing
          </Link>
        </div>

        {/* Sign Out Section */}
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <LogOut size={20} />
            Sign Out
          </h2>
          <p className="text-slate-400 mb-4">
            Sign out of your PISAMA account.
          </p>
          <button
            onClick={handleSignOut}
            className="inline-flex items-center gap-2 px-4 py-2 bg-red-500/20 text-red-400 border border-red-500/50 rounded-lg hover:bg-red-500/30 transition-colors"
          >
            <LogOut size={16} />
            Sign Out
          </button>
        </div>
      </div>
    </Layout>
  )
}
