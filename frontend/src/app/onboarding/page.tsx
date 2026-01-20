'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  CheckCircle2,
  Circle,
  ArrowRight,
  ArrowLeft,
  Shield,
  Zap,
  Link2,
  Play,
  Copy,
  Check,
  ExternalLink,
  GitBranch,
  Code2,
  Users,
  type LucideIcon
} from 'lucide-react'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { useUserPreferences, type UserType } from '@/lib/user-preferences'

interface Step {
  id: number
  title: string
  description: string
  icon: LucideIcon
}

const steps: Step[] = [
  {
    id: 1,
    title: 'Who Are You?',
    description: 'Help us customize your experience',
    icon: Users
  },
  {
    id: 2,
    title: 'Welcome',
    description: 'Let\'s set up your workflow monitoring in just a few minutes',
    icon: Shield
  },
  {
    id: 3,
    title: 'Connect Your n8n',
    description: 'Link your n8n instance so we can help fix problems automatically',
    icon: Link2
  },
  {
    id: 4,
    title: 'Add Monitoring',
    description: 'Add a simple node to your n8n workflow to send us data',
    icon: Zap
  },
  {
    id: 5,
    title: 'You\'re Ready!',
    description: 'Start monitoring your workflows and let us find and fix issues',
    icon: Play
  }
]

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <button
      onClick={handleCopy}
      className="p-2 hover:bg-slate-700 rounded transition-colors"
      title="Copy to clipboard"
    >
      {copied ? (
        <Check size={16} className="text-green-400" />
      ) : (
        <Copy size={16} className="text-slate-400" />
      )}
    </button>
  )
}

function StepUserType({
  selectedType,
  onSelect
}: {
  selectedType: UserType
  onSelect: (type: UserType) => void
}) {
  return (
    <div className="space-y-6">
      <div className="text-center">
        <Users size={64} className="mx-auto mb-4 text-blue-500" />
        <h2 className="text-2xl font-bold text-white mb-2">How do you build automations?</h2>
        <p className="text-slate-400 max-w-md mx-auto">
          This helps us show you the right features and use language you'll understand.
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-6 max-w-2xl mx-auto mt-8">
        <button
          onClick={() => onSelect('n8n_user')}
          className={`text-left p-6 rounded-xl border-2 transition-all ${
            selectedType === 'n8n_user'
              ? 'border-blue-500 bg-blue-500/10'
              : 'border-slate-700 hover:border-slate-600 bg-slate-800/50'
          }`}
        >
          <div className="w-14 h-14 bg-amber-500/20 rounded-xl flex items-center justify-center mb-4">
            <GitBranch size={28} className="text-amber-400" />
          </div>
          <h3 className="text-lg font-semibold text-white mb-2">n8n / Visual Workflows</h3>
          <p className="text-sm text-slate-400 mb-4">
            I use n8n, Dify, Flowise, or similar visual automation tools.
            I prefer simple interfaces and don't write much code.
          </p>
          <div className="flex flex-wrap gap-2">
            <span className="text-xs bg-slate-700 text-slate-300 px-2 py-1 rounded">n8n</span>
            <span className="text-xs bg-slate-700 text-slate-300 px-2 py-1 rounded">Dify</span>
            <span className="text-xs bg-slate-700 text-slate-300 px-2 py-1 rounded">Flowise</span>
          </div>
        </button>

        <button
          onClick={() => onSelect('developer')}
          className={`text-left p-6 rounded-xl border-2 transition-all ${
            selectedType === 'developer'
              ? 'border-blue-500 bg-blue-500/10'
              : 'border-slate-700 hover:border-slate-600 bg-slate-800/50'
          }`}
        >
          <div className="w-14 h-14 bg-green-500/20 rounded-xl flex items-center justify-center mb-4">
            <Code2 size={28} className="text-green-400" />
          </div>
          <h3 className="text-lg font-semibold text-white mb-2">Developer / Code-first</h3>
          <p className="text-sm text-slate-400 mb-4">
            I build AI agents with code using frameworks like LangGraph, AutoGen, or CrewAI.
            I'm comfortable with APIs and debugging.
          </p>
          <div className="flex flex-wrap gap-2">
            <span className="text-xs bg-slate-700 text-slate-300 px-2 py-1 rounded">LangGraph</span>
            <span className="text-xs bg-slate-700 text-slate-300 px-2 py-1 rounded">AutoGen</span>
            <span className="text-xs bg-slate-700 text-slate-300 px-2 py-1 rounded">CrewAI</span>
          </div>
        </button>
      </div>

      <p className="text-center text-xs text-slate-500 mt-6">
        You can always change this later in Settings
      </p>
    </div>
  )
}

function StepWelcome() {
  return (
    <div className="space-y-6">
      <div className="text-center">
        <Shield size={64} className="mx-auto mb-4 text-blue-500" />
        <h2 className="text-2xl font-bold text-white mb-2">Welcome to MAO Testing</h2>
        <p className="text-slate-400 max-w-md mx-auto">
          We help you find and fix problems in your AI workflows automatically.
          No coding required!
        </p>
      </div>

      <div className="grid md:grid-cols-3 gap-4 mt-8">
        <Card>
          <CardContent className="p-4 text-center">
            <div className="w-12 h-12 bg-blue-500/20 rounded-lg flex items-center justify-center mx-auto mb-3">
              <Zap size={24} className="text-blue-400" />
            </div>
            <h3 className="text-sm font-medium text-white mb-1">Find Problems</h3>
            <p className="text-xs text-slate-400">
              We automatically detect when something goes wrong in your workflows
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 text-center">
            <div className="w-12 h-12 bg-green-500/20 rounded-lg flex items-center justify-center mx-auto mb-3">
              <Shield size={24} className="text-green-400" />
            </div>
            <h3 className="text-sm font-medium text-white mb-1">Fix Automatically</h3>
            <p className="text-xs text-slate-400">
              We suggest fixes and can apply them to your workflows for you
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 text-center">
            <div className="w-12 h-12 bg-amber-500/20 rounded-lg flex items-center justify-center mx-auto mb-3">
              <Play size={24} className="text-amber-400" />
            </div>
            <h3 className="text-sm font-medium text-white mb-1">Test First</h3>
            <p className="text-xs text-slate-400">
              Preview and test any fix before it goes live - you're always in control
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function StepConnectN8n() {
  const [n8nUrl, setN8nUrl] = useState('')
  const [apiKey, setApiKey] = useState('')

  return (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <Link2 size={48} className="mx-auto mb-4 text-blue-500" />
        <h2 className="text-xl font-bold text-white mb-2">Connect Your n8n Instance</h2>
        <p className="text-slate-400">
          This lets us apply fixes directly to your workflows
        </p>
      </div>

      <div className="max-w-md mx-auto space-y-4">
        <div>
          <label className="block text-sm text-slate-400 mb-2">
            Your n8n URL
            <span className="text-slate-500 ml-1">(e.g., https://your-name.app.n8n.cloud)</span>
          </label>
          <input
            type="url"
            value={n8nUrl}
            onChange={(e) => setN8nUrl(e.target.value)}
            placeholder="https://your-instance.app.n8n.cloud"
            className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder:text-slate-500 focus:outline-none focus:border-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm text-slate-400 mb-2">
            n8n API Key
            <a
              href="https://docs.n8n.io/api/authentication/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-400 hover:underline ml-2 inline-flex items-center gap-1"
            >
              How to get this? <ExternalLink size={12} />
            </a>
          </label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="n8n_api_..."
            className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder:text-slate-500 focus:outline-none focus:border-blue-500"
          />
        </div>

        <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-4">
          <p className="text-sm text-blue-300">
            <strong>Don't have n8n yet?</strong> You can skip this step and connect later
            from Settings → Integrations.
          </p>
        </div>
      </div>
    </div>
  )
}

function StepAddMonitoring() {
  const webhookUrl = 'https://api.mao-testing.com/v1/ingest/n8n/webhook'

  return (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <Zap size={48} className="mx-auto mb-4 text-amber-500" />
        <h2 className="text-xl font-bold text-white mb-2">Add Monitoring to Your Workflow</h2>
        <p className="text-slate-400">
          Add one node to send us workflow data - takes less than a minute!
        </p>
      </div>

      <div className="max-w-lg mx-auto space-y-6">
        <div className="space-y-4">
          <div className="flex items-start gap-4">
            <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center flex-shrink-0 text-white font-bold">
              1
            </div>
            <div>
              <h3 className="text-sm font-medium text-white mb-1">Open your workflow in n8n</h3>
              <p className="text-xs text-slate-400">
                Open the workflow you want to monitor
              </p>
            </div>
          </div>

          <div className="flex items-start gap-4">
            <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center flex-shrink-0 text-white font-bold">
              2
            </div>
            <div>
              <h3 className="text-sm font-medium text-white mb-1">Add an HTTP Request node</h3>
              <p className="text-xs text-slate-400">
                Click the + button and search for "HTTP Request"
              </p>
            </div>
          </div>

          <div className="flex items-start gap-4">
            <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center flex-shrink-0 text-white font-bold">
              3
            </div>
            <div className="flex-1">
              <h3 className="text-sm font-medium text-white mb-1">Configure with this URL</h3>
              <div className="flex items-center gap-2 bg-slate-800 rounded-lg p-3 mt-2">
                <code className="text-xs text-green-400 flex-1 overflow-x-auto">
                  {webhookUrl}
                </code>
                <CopyButton text={webhookUrl} />
              </div>
              <p className="text-xs text-slate-500 mt-2">
                Set Method to POST and paste this URL
              </p>
            </div>
          </div>

          <div className="flex items-start gap-4">
            <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center flex-shrink-0 text-white font-bold">
              4
            </div>
            <div>
              <h3 className="text-sm font-medium text-white mb-1">Connect it to your workflow</h3>
              <p className="text-xs text-slate-400">
                Connect the HTTP Request after your main workflow steps
              </p>
            </div>
          </div>
        </div>

        <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-4">
          <p className="text-sm text-amber-300">
            <strong>That's it!</strong> Your workflow will now send us data so we can watch for problems.
          </p>
        </div>
      </div>
    </div>
  )
}

function StepComplete() {
  return (
    <div className="space-y-6 text-center">
      <div>
        <CheckCircle2 size={64} className="mx-auto mb-4 text-green-500" />
        <h2 className="text-2xl font-bold text-white mb-2">You're All Set!</h2>
        <p className="text-slate-400 max-w-md mx-auto">
          Your workflows are now being monitored. We'll let you know if we find any problems.
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-4 max-w-lg mx-auto mt-8">
        <Card className="hover:border-blue-500/50 transition-colors cursor-pointer">
          <CardContent className="p-4">
            <h3 className="text-sm font-medium text-white mb-1">View Dashboard</h3>
            <p className="text-xs text-slate-400">
              See all your workflow runs and any issues we've found
            </p>
          </CardContent>
        </Card>

        <Card className="hover:border-blue-500/50 transition-colors cursor-pointer">
          <CardContent className="p-4">
            <h3 className="text-sm font-medium text-white mb-1">Connect More Workflows</h3>
            <p className="text-xs text-slate-400">
              Add monitoring to your other n8n workflows
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-4 max-w-md mx-auto">
        <p className="text-sm text-green-300">
          <strong>Need help?</strong> Check out our docs or reach out to support.
          We're here to help!
        </p>
      </div>
    </div>
  )
}

export default function OnboardingPage() {
  const router = useRouter()
  const { setUserType, preferences } = useUserPreferences()
  const [currentStep, setCurrentStep] = useState(1)
  const [selectedUserType, setSelectedUserType] = useState<UserType>(preferences.userType)

  const handleUserTypeSelect = (type: UserType) => {
    setSelectedUserType(type)
    setUserType(type)
  }

  const handleNext = () => {
    // On step 1, require user type selection
    if (currentStep === 1 && !selectedUserType) {
      return
    }

    if (currentStep < steps.length) {
      setCurrentStep(currentStep + 1)
    } else {
      router.push('/dashboard')
    }
  }

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1)
    }
  }

  const handleSkip = () => {
    // If skipping without selecting user type, default to n8n_user for simplest experience
    if (!selectedUserType) {
      setUserType('n8n_user')
    }
    router.push('/dashboard')
  }

  const renderStepContent = () => {
    switch (currentStep) {
      case 1:
        return <StepUserType selectedType={selectedUserType} onSelect={handleUserTypeSelect} />
      case 2:
        return <StepWelcome />
      case 3:
        return <StepConnectN8n />
      case 4:
        return <StepAddMonitoring />
      case 5:
        return <StepComplete />
      default:
        return <StepUserType selectedType={selectedUserType} onSelect={handleUserTypeSelect} />
    }
  }

  // Disable next button on step 1 if no user type selected
  const isNextDisabled = currentStep === 1 && !selectedUserType

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col">
      {/* Header */}
      <header className="border-b border-slate-800 p-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className="h-8 w-8 text-blue-500" />
            <span className="text-xl font-bold text-white">MAO Testing</span>
          </div>
          <Button variant="ghost" size="sm" onClick={handleSkip}>
            Skip Setup
          </Button>
        </div>
      </header>

      {/* Progress */}
      <div className="border-b border-slate-800 py-4">
        <div className="max-w-4xl mx-auto px-4">
          <div className="flex items-center justify-between">
            {steps.map((step, idx) => (
              <div
                key={step.id}
                className="flex items-center"
              >
                <div className="flex items-center gap-2">
                  {currentStep > step.id ? (
                    <CheckCircle2 size={24} className="text-green-500" />
                  ) : currentStep === step.id ? (
                    <div className="w-6 h-6 bg-blue-500 rounded-full flex items-center justify-center text-white text-xs font-bold">
                      {step.id}
                    </div>
                  ) : (
                    <Circle size={24} className="text-slate-600" />
                  )}
                  <span className={`text-sm hidden md:inline ${
                    currentStep >= step.id ? 'text-white' : 'text-slate-500'
                  }`}>
                    {step.title}
                  </span>
                </div>
                {idx < steps.length - 1 && (
                  <div className={`w-12 md:w-24 h-0.5 mx-2 ${
                    currentStep > step.id ? 'bg-green-500' : 'bg-slate-700'
                  }`} />
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <main className="flex-1 p-8">
        <div className="max-w-4xl mx-auto">
          {renderStepContent()}
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 p-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <Button
            variant="ghost"
            onClick={handleBack}
            disabled={currentStep === 1}
            leftIcon={<ArrowLeft size={16} />}
          >
            Back
          </Button>

          <span className="text-sm text-slate-500">
            Step {currentStep} of {steps.length}
          </span>

          <Button
            variant="primary"
            onClick={handleNext}
            disabled={isNextDisabled}
            rightIcon={<ArrowRight size={16} />}
          >
            {currentStep === steps.length ? 'Go to Dashboard' : 'Continue'}
          </Button>
        </div>
      </footer>
    </div>
  )
}
