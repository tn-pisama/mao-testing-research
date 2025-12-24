'use client'

import { useState } from 'react'
import { X, ArrowRight, Bot, Workflow, AlertTriangle, BarChart3, Check } from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/Button'

interface WelcomeModalProps {
  isOpen: boolean
  onClose: () => void
  onComplete: () => void
}

const steps = [
  {
    icon: Bot,
    title: 'Multi-Agent Orchestration',
    description: 'Monitor and visualize your AI agent systems in real-time. See how agents communicate, delegate tasks, and coordinate their work.',
    color: 'text-purple-400',
    bgColor: 'bg-purple-500/20',
  },
  {
    icon: AlertTriangle,
    title: 'Failure Detection',
    description: 'Automatically detect infinite loops, state corruption, persona drift, and coordination deadlocks before they impact your users.',
    color: 'text-red-400',
    bgColor: 'bg-red-500/20',
  },
  {
    icon: Workflow,
    title: 'Trace Analysis',
    description: 'Deep dive into execution traces. Understand state transitions, token usage, and latency patterns across your agent workflows.',
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/20',
  },
  {
    icon: BarChart3,
    title: 'Analytics & Insights',
    description: 'Track costs, performance metrics, and failure patterns over time. Make data-driven decisions to improve your agent systems.',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/20',
  },
]

export function WelcomeModal({ isOpen, onClose, onComplete }: WelcomeModalProps) {
  const [currentStep, setCurrentStep] = useState(0)

  if (!isOpen) return null

  const step = steps[currentStep]
  const StepIcon = step.icon
  const isLastStep = currentStep === steps.length - 1

  const handleNext = () => {
    if (isLastStep) {
      onComplete()
      onClose()
    } else {
      setCurrentStep((prev) => prev + 1)
    }
  }

  const handleSkip = () => {
    onComplete()
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      
      <div className="relative w-full max-w-lg bg-slate-800 rounded-2xl border border-slate-700 shadow-2xl overflow-hidden animate-scale-in">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 text-slate-400 hover:text-white transition-colors"
        >
          <X size={20} />
        </button>

        <div className="p-8">
          <div className="flex justify-center mb-6">
            <div className={clsx('p-4 rounded-2xl', step.bgColor)}>
              <StepIcon size={40} className={step.color} />
            </div>
          </div>

          <div className="text-center mb-8">
            <h2 className="text-2xl font-bold text-white mb-3">{step.title}</h2>
            <p className="text-slate-400">{step.description}</p>
          </div>

          <div className="flex justify-center gap-2 mb-8">
            {steps.map((_, index) => (
              <button
                key={index}
                onClick={() => setCurrentStep(index)}
                className={clsx(
                  'w-2 h-2 rounded-full transition-all',
                  index === currentStep
                    ? 'w-6 bg-primary-500'
                    : index < currentStep
                    ? 'bg-primary-500/50'
                    : 'bg-slate-600'
                )}
              />
            ))}
          </div>

          <div className="flex items-center justify-between">
            <button
              onClick={handleSkip}
              className="text-sm text-slate-400 hover:text-white transition-colors"
            >
              Skip tour
            </button>
            <Button
              onClick={handleNext}
              rightIcon={isLastStep ? <Check size={16} /> : <ArrowRight size={16} />}
            >
              {isLastStep ? 'Get Started' : 'Next'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
