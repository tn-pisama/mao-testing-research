'use client'

import { useRouter } from 'next/navigation'
import { Shield } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { useOnboarding } from '@/hooks/useOnboarding'
import { OnboardingProgress } from '@/components/onboarding/OnboardingProgress'
import { StepConnect } from '@/components/onboarding/StepConnect'
import { StepFirstTrace } from '@/components/onboarding/StepFirstTrace'
import { StepFirstDetection } from '@/components/onboarding/StepFirstDetection'
import { useSafeAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import { createApiClient } from '@/lib/api'

export default function OnboardingPage() {
  const router = useRouter()
  const { getToken: _getToken } = useSafeAuth()
  const { tenantId } = useTenant()
  // API client will be created lazily when needed (getToken is async)
  // For onboarding steps that need the API, we pass a factory
  const apiClient = createApiClient(null, tenantId)

  const {
    currentStep,
    selectedFramework,
    firstTraceId,
    setStep,
    selectFramework,
    markTraceReceived,
    markDetectionsRun,
    completeOnboarding,
  } = useOnboarding()

  const handleSkip = () => {
    completeOnboarding()
    router.push('/dashboard')
  }

  const handleSkipToDemo = () => {
    completeOnboarding()
    router.push('/demo')
  }

  const handleComplete = () => {
    markDetectionsRun()
    completeOnboarding()
    router.push('/dashboard')
  }

  return (
    <div className="min-h-screen bg-zinc-950 flex flex-col">
      {/* Header */}
      <header className="border-b border-zinc-800 p-4">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className="h-8 w-8 text-blue-500" />
            <span className="text-xl font-bold text-white">PISAMA</span>
          </div>
          <Button variant="ghost" size="sm" onClick={handleSkip}>
            Skip Setup
          </Button>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 p-8">
        <div className="max-w-3xl mx-auto">
          <OnboardingProgress currentStep={currentStep} />

          {currentStep === 1 && (
            <StepConnect
              selectedFramework={selectedFramework}
              onSelectFramework={selectFramework}
              onNext={() => setStep(2)}
            />
          )}

          {currentStep === 2 && (
            <StepFirstTrace
              apiClient={apiClient}
              onTraceReceived={markTraceReceived}
              onSkipToDemo={handleSkipToDemo}
            />
          )}

          {currentStep === 3 && firstTraceId && (
            <StepFirstDetection
              apiClient={apiClient}
              traceId={firstTraceId}
              onComplete={handleComplete}
            />
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-800 p-4">
        <div className="max-w-3xl mx-auto flex items-center justify-center">
          <span className="text-sm text-zinc-500">
            Step {currentStep} of 3
          </span>
        </div>
      </footer>
    </div>
  )
}
