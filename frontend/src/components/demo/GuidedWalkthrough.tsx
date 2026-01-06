'use client'

import { useState, useEffect } from 'react'
import { X, ChevronRight, ChevronLeft, Sparkles, Play, AlertTriangle, Wrench, CheckCircle } from 'lucide-react'
import { Button } from '@/components/ui/Button'

interface WalkthroughStep {
  id: string
  title: string
  description: string
  target?: string // CSS selector for highlighting
  position: 'top' | 'bottom' | 'left' | 'right' | 'center'
  action?: string
  icon: typeof Play
}

const WALKTHROUGH_STEPS: WalkthroughStep[] = [
  {
    id: 'welcome',
    title: 'Welcome to PISAMA Demo',
    description: 'This interactive demo shows how PISAMA detects agent failures in real-time. Let\'s walk through the key features.',
    position: 'center',
    icon: Sparkles,
  },
  {
    id: 'scenarios',
    title: 'Choose a Scenario',
    description: 'Select from different failure scenarios: Healthy workflow, Infinite Loop, State Corruption, or Coordination Deadlock.',
    target: '.scenario-selector',
    position: 'bottom',
    action: 'Click any scenario card to select it',
    icon: Play,
  },
  {
    id: 'start',
    title: 'Start the Demo',
    description: 'Click "Start Demo" to begin the simulation. Watch as agents execute their tasks.',
    target: '.demo-start-button',
    position: 'bottom',
    action: 'Click Start Demo',
    icon: Play,
  },
  {
    id: 'metrics',
    title: 'Real-time Metrics',
    description: 'Monitor agent metrics as they work: active agents, messages exchanged, tokens used, and costs.',
    target: '.metrics-panel',
    position: 'bottom',
    icon: Sparkles,
  },
  {
    id: 'detection',
    title: 'Failure Detection',
    description: 'When a failure is detected, you\'ll see an alert appear. PISAMA identifies the failure type, confidence level, and root cause.',
    target: '.detection-feed',
    position: 'left',
    icon: AlertTriangle,
  },
  {
    id: 'fix',
    title: 'One-Click Fix',
    description: 'Click "Apply Fix" to see the suggested remediation. PISAMA generates context-aware fixes based on the failure type.',
    target: '.fix-button',
    position: 'left',
    action: 'Click Apply Fix',
    icon: Wrench,
  },
  {
    id: 'complete',
    title: 'You\'re Ready!',
    description: 'That\'s the core of PISAMA. Install it in your own project to start detecting and preventing agent failures.',
    position: 'center',
    icon: CheckCircle,
  },
]

interface GuidedWalkthroughProps {
  onComplete: () => void
  onSkip: () => void
}

export function GuidedWalkthrough({ onComplete, onSkip }: GuidedWalkthroughProps) {
  const [currentStep, setCurrentStep] = useState(0)
  const [isVisible, setIsVisible] = useState(true)

  const step = WALKTHROUGH_STEPS[currentStep]
  const isLastStep = currentStep === WALKTHROUGH_STEPS.length - 1
  const isFirstStep = currentStep === 0

  const handleNext = () => {
    if (isLastStep) {
      setIsVisible(false)
      onComplete()
    } else {
      setCurrentStep(prev => prev + 1)
    }
  }

  const handlePrev = () => {
    if (!isFirstStep) {
      setCurrentStep(prev => prev - 1)
    }
  }

  const handleSkip = () => {
    setIsVisible(false)
    onSkip()
  }

  useEffect(() => {
    // Highlight target element if specified
    if (step.target) {
      const element = document.querySelector(step.target)
      if (element) {
        element.classList.add('walkthrough-highlight')
        return () => element.classList.remove('walkthrough-highlight')
      }
    }
  }, [step.target])

  if (!isVisible) return null

  const Icon = step.icon

  return (
    <>
      {/* Overlay */}
      <div className="fixed inset-0 bg-black/60 z-40" />

      {/* Tooltip */}
      <div className={`fixed z-50 ${
        step.position === 'center'
          ? 'top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2'
          : 'top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2'
      }`}>
        <div className="bg-slate-800 rounded-xl border border-slate-600 shadow-2xl w-[400px] overflow-hidden">
          {/* Header */}
          <div className="px-5 py-4 border-b border-slate-700 flex items-center justify-between bg-gradient-to-r from-indigo-600/20 to-purple-600/20">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-indigo-500/20">
                <Icon size={20} className="text-indigo-400" />
              </div>
              <div>
                <h3 className="font-semibold text-white">{step.title}</h3>
                <span className="text-xs text-slate-400">
                  Step {currentStep + 1} of {WALKTHROUGH_STEPS.length}
                </span>
              </div>
            </div>
            <button
              onClick={handleSkip}
              className="p-1 text-slate-400 hover:text-white transition-colors"
            >
              <X size={18} />
            </button>
          </div>

          {/* Content */}
          <div className="px-5 py-4">
            <p className="text-slate-300 text-sm leading-relaxed">
              {step.description}
            </p>
            {step.action && (
              <div className="mt-3 px-3 py-2 rounded-lg bg-indigo-500/10 border border-indigo-500/30">
                <span className="text-xs text-indigo-300 font-medium">
                  Action: {step.action}
                </span>
              </div>
            )}
          </div>

          {/* Progress */}
          <div className="px-5 pb-2">
            <div className="flex gap-1">
              {WALKTHROUGH_STEPS.map((_, i) => (
                <div
                  key={i}
                  className={`h-1 flex-1 rounded-full ${
                    i <= currentStep ? 'bg-indigo-500' : 'bg-slate-700'
                  }`}
                />
              ))}
            </div>
          </div>

          {/* Navigation */}
          <div className="px-5 py-4 border-t border-slate-700 flex items-center justify-between">
            <button
              onClick={handleSkip}
              className="text-sm text-slate-400 hover:text-white transition-colors"
            >
              Skip tour
            </button>
            <div className="flex items-center gap-2">
              {!isFirstStep && (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handlePrev}
                  leftIcon={<ChevronLeft size={16} />}
                >
                  Back
                </Button>
              )}
              <Button
                size="sm"
                onClick={handleNext}
                rightIcon={!isLastStep ? <ChevronRight size={16} /> : undefined}
              >
                {isLastStep ? 'Get Started' : 'Next'}
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* CSS for highlight effect */}
      <style jsx global>{`
        .walkthrough-highlight {
          position: relative;
          z-index: 45;
          box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.5), 0 0 20px rgba(99, 102, 241, 0.3);
          border-radius: 12px;
        }
      `}</style>
    </>
  )
}

export function WalkthroughTrigger({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2 px-3 py-1.5 text-sm text-indigo-400 hover:text-indigo-300 bg-indigo-500/10 hover:bg-indigo-500/20 rounded-lg border border-indigo-500/30 transition-colors"
    >
      <Sparkles size={14} />
      Take the Tour
    </button>
  )
}
