'use client'

import { CheckCircle2, Circle } from 'lucide-react'
import type { OnboardingStep } from '@/hooks/useOnboarding'

const STEPS = [
  { id: 1 as OnboardingStep, title: 'Connect' },
  { id: 2 as OnboardingStep, title: 'First Trace' },
  { id: 3 as OnboardingStep, title: 'First Detection' },
]

interface OnboardingProgressProps {
  currentStep: OnboardingStep
}

export function OnboardingProgress({ currentStep }: OnboardingProgressProps) {
  return (
    <div className="flex items-center justify-center gap-2 mb-8">
      {STEPS.map((step, i) => (
        <div key={step.id} className="flex items-center">
          <div className="flex items-center gap-2">
            {step.id < currentStep ? (
              <CheckCircle2 className="w-6 h-6 text-green-500" />
            ) : step.id === currentStep ? (
              <div className="w-6 h-6 rounded-full bg-blue-500 flex items-center justify-center text-white text-xs font-bold">
                {step.id}
              </div>
            ) : (
              <Circle className="w-6 h-6 text-zinc-600" />
            )}
            <span
              className={`text-sm font-medium ${
                step.id <= currentStep ? 'text-zinc-100' : 'text-zinc-500'
              }`}
            >
              {step.title}
            </span>
          </div>
          {i < STEPS.length - 1 && (
            <div
              className={`w-12 h-0.5 mx-3 ${
                step.id < currentStep ? 'bg-green-500' : 'bg-zinc-700'
              }`}
            />
          )}
        </div>
      ))}
    </div>
  )
}
