'use client'

import { useState } from 'react'
import { Button } from '../ui/Button'
import { ArrowRight, ArrowLeft, X, Compass } from 'lucide-react'

interface GuidedWalkthroughProps {
  step?: number
  onNext?: () => void
  onComplete: () => void
  onSkip: () => void
}

const TOUR_STEPS = [
  {
    title: 'Choose a Scenario',
    description:
      'Select from 5 curated failure scenarios. Each demonstrates a different type of AI agent failure that PISAMA can detect.',
    target: '.scenario-selector',
  },
  {
    title: 'Start the Demo',
    description:
      'Click "Start Demo" to begin the simulation. Watch as agent states are processed and analyzed in real-time.',
    target: '.demo-start-button',
  },
  {
    title: 'Watch Metrics Update',
    description:
      'The metrics panel shows token usage, latency, error rates, and active agent counts — all updating live.',
    target: '.metrics-panel',
  },
  {
    title: 'See Detections Arrive',
    description:
      'When issues are found, detection cards appear in the feed with type badges, confidence scores, and explanations.',
    target: '.detection-feed',
  },
  {
    title: 'Explore Traces',
    description:
      'Click on any trace to see the full agent state timeline, including where loops, corruption, or drift occurred.',
    target: '.trace-upload',
  },
]

export function GuidedWalkthrough({ onComplete, onSkip }: GuidedWalkthroughProps) {
  const [currentStep, setCurrentStep] = useState(0)
  const step = TOUR_STEPS[currentStep]

  const handleNext = () => {
    if (currentStep < TOUR_STEPS.length - 1) {
      setCurrentStep(currentStep + 1)
    } else {
      onComplete()
    }
  }

  const handlePrev = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onSkip} />

      {/* Tour card */}
      <div className="relative bg-zinc-900 border border-zinc-700 rounded-xl shadow-2xl max-w-md w-full mx-4 p-6">
        {/* Close button */}
        <button
          onClick={onSkip}
          className="absolute top-3 right-3 p-1 text-zinc-500 hover:text-zinc-300 transition-colors"
        >
          <X size={16} />
        </button>

        {/* Step indicator */}
        <div className="flex items-center gap-1.5 mb-4">
          {TOUR_STEPS.map((_, i) => (
            <div
              key={i}
              className={`h-1 flex-1 rounded-full transition-colors ${
                i <= currentStep ? 'bg-blue-500' : 'bg-zinc-700'
              }`}
            />
          ))}
        </div>

        {/* Content */}
        <div className="flex items-start gap-3 mb-6">
          <div className="p-2 rounded-lg bg-blue-500/10">
            <Compass size={20} className="text-blue-400" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-zinc-100">{step.title}</h3>
            <p className="text-sm text-zinc-400 mt-1">{step.description}</p>
          </div>
        </div>

        {/* Step counter */}
        <p className="text-xs text-zinc-600 mb-4">
          Step {currentStep + 1} of {TOUR_STEPS.length}
        </p>

        {/* Navigation */}
        <div className="flex items-center justify-between">
          <Button
            variant="ghost"
            size="sm"
            onClick={handlePrev}
            disabled={currentStep === 0}
          >
            <ArrowLeft size={14} className="mr-1" />
            Back
          </Button>
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={onSkip}>
              Skip Tour
            </Button>
            <Button size="sm" onClick={handleNext}>
              {currentStep < TOUR_STEPS.length - 1 ? (
                <>
                  Next
                  <ArrowRight size={14} className="ml-1" />
                </>
              ) : (
                'Get Started'
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

export function WalkthroughTrigger({ onClick }: { onClick?: () => void }) {
  return (
    <Button variant="ghost" size="sm" onClick={onClick}>
      <Compass size={14} className="mr-1" />
      Take a Tour
    </Button>
  )
}
