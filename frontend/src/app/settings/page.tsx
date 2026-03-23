'use client'

export const dynamic = 'force-dynamic'

import { useState } from 'react'
import { Layout } from '@/components/common/Layout'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Switch } from '@/components/ui/Switch'
import { Label } from '@/components/ui/Label'
import {
  Settings,
  Key,
  Bell,
  Shield,
  Webhook,
  Code,
  Save,
  Copy,
  Eye,
  EyeOff,
  Check,
  RefreshCw,
  Sliders,
  ExternalLink,
  Code2,
} from 'lucide-react'
import Link from 'next/link'
import { useUserPreferences } from '@/lib/user-preferences'

type SettingsTab = 'general' | 'api' | 'notifications' | 'detection' | 'integrations'

const tabs: { id: SettingsTab; label: string; icon: typeof Settings }[] = [
  { id: 'general', label: 'General', icon: Settings },
  { id: 'api', label: 'API Keys', icon: Key },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'detection', label: 'Detection', icon: Shield },
  { id: 'integrations', label: 'Integrations', icon: Webhook },
]

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('general')
  const [showApiKey, setShowApiKey] = useState(false)
  const [saved, setSaved] = useState(false)
  const { preferences, setDeveloperMode, setUserType, isN8nUser } = useUserPreferences()

  const handleSave = () => {
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <Layout>
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white mb-1">Settings</h1>
            <p className="text-sm text-zinc-400">
              Configure your PISAMA preferences
            </p>
          </div>
          <Button
            onClick={handleSave}
            variant={saved ? 'success' : 'primary'}
          >
            {saved ? <Check size={16} className="mr-2" /> : <Save size={16} className="mr-2" />}
            {saved ? 'Saved!' : 'Save Changes'}
          </Button>
        </div>

        <div className="flex gap-6">
          <div className="w-48 flex-shrink-0">
            <nav className="space-y-1" role="tablist">
              {tabs.map((tab) => {
                const Icon = tab.icon
                return (
                  <button
                    key={tab.id}
                    role="tab"
                    aria-selected={activeTab === tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={cn(
                      'w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                      activeTab === tab.id
                        ? 'bg-blue-600 text-white'
                        : 'text-zinc-400 hover:text-white hover:bg-zinc-800'
                    )}
                  >
                    <Icon size={16} />
                    {tab.label}
                  </button>
                )
              })}
            </nav>
          </div>

          <div className="flex-1">
            {activeTab === 'general' && (
              <div className="space-y-6">
                <SettingsSection title="Workspace" description="Manage your workspace settings">
                  <SettingsField label="Workspace Name">
                    <Input defaultValue="My Workspace" />
                  </SettingsField>
                  <SettingsField label="Timezone">
                    <Select>
                      <option>UTC</option>
                      <option>America/New_York</option>
                      <option>America/Los_Angeles</option>
                      <option>Europe/London</option>
                      <option>Europe/Helsinki</option>
                      <option>Asia/Tokyo</option>
                    </Select>
                  </SettingsField>
                </SettingsSection>

                <SettingsSection title="Data Retention" description="Configure how long data is stored">
                  <SettingsField label="Run Retention (days)">
                    <Input type="number" defaultValue={30} className="w-32" />
                  </SettingsField>
                  <SettingsField label="Detection Retention (days)">
                    <Input type="number" defaultValue={90} className="w-32" />
                  </SettingsField>
                </SettingsSection>

                <SettingsSection
                  title="Experience Mode"
                  description="Choose between simplified or full-featured interface"
                >
                  <div className="space-y-4">
                    <SettingsField label="Your Role">
                      <div className="flex gap-3">
                        <button
                          onClick={() => setUserType('n8n_user')}
                          className={cn(
                            'flex-1 p-3 rounded-lg border-2 transition-all text-left',
                            preferences.userType === 'n8n_user'
                              ? 'border-blue-500 bg-blue-500/10'
                              : 'border-zinc-700 hover:border-zinc-600'
                          )}
                        >
                          <div className="text-sm font-medium text-white">n8n / Workflows</div>
                          <div className="text-xs text-zinc-400">Simplified, visual interface</div>
                        </button>
                        <button
                          onClick={() => setUserType('developer')}
                          className={cn(
                            'flex-1 p-3 rounded-lg border-2 transition-all text-left',
                            preferences.userType === 'developer'
                              ? 'border-blue-500 bg-blue-500/10'
                              : 'border-zinc-700 hover:border-zinc-600'
                          )}
                        >
                          <div className="text-sm font-medium text-white">Developer</div>
                          <div className="text-xs text-zinc-400">Full-featured, technical</div>
                        </button>
                      </div>
                    </SettingsField>

                    {isN8nUser && (
                      <div className="p-4 rounded-lg bg-zinc-900 border border-zinc-800">
                        <div className="flex items-start gap-3">
                          <Switch
                            checked={preferences.developerMode}
                            onCheckedChange={setDeveloperMode}
                            className="mt-1"
                          />
                          <div>
                            <div className="text-sm font-medium text-white flex items-center gap-2">
                              <Code2 size={16} />
                              Developer Mode
                            </div>
                            <div className="text-xs text-zinc-400">
                              Show advanced features like Runs, Agents, and raw data views.
                              Turn this on if you want access to technical debugging tools.
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </SettingsSection>
              </div>
            )}

            {activeTab === 'api' && (
              <div className="space-y-6">
                <SettingsSection title="API Key" description="Use this key to authenticate with the PISAMA API">
                  <div className="p-4 rounded-lg bg-zinc-900 border border-zinc-800">
                    <div className="flex items-center gap-3">
                      <div className="flex-1 font-mono text-sm text-zinc-300">
                        {showApiKey ? 'mao_sk_1234567890abcdefghijklmnop' : '••••••••••••••••••••••••••••••'}
                      </div>
                      <button
                        onClick={() => setShowApiKey(!showApiKey)}
                        className="p-2 text-zinc-400 hover:text-white transition-colors"
                        aria-label={showApiKey ? 'Hide API key' : 'Show API key'}
                      >
                        {showApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                      <button
                        onClick={() => navigator.clipboard.writeText('mao_sk_1234567890abcdefghijklmnop')}
                        className="p-2 text-zinc-400 hover:text-white transition-colors"
                        aria-label="Copy API key"
                      >
                        <Copy size={16} />
                      </button>
                    </div>
                  </div>
                  <div className="flex gap-3 mt-4">
                    <Button variant="secondary" size="sm">
                      <RefreshCw size={14} className="mr-2" />
                      Regenerate Key
                    </Button>
                  </div>
                </SettingsSection>

                <SettingsSection title="Usage" description="API usage for current billing period">
                  <div className="grid grid-cols-3 gap-4">
                    <div className="p-4 rounded-lg bg-zinc-900 border border-zinc-800">
                      <div className="text-2xl font-bold text-white">12,450</div>
                      <div className="text-xs text-zinc-400">API Calls</div>
                    </div>
                    <div className="p-4 rounded-lg bg-zinc-900 border border-zinc-800">
                      <div className="text-2xl font-bold text-white">847</div>
                      <div className="text-xs text-zinc-400">Traces Processed</div>
                    </div>
                    <div className="p-4 rounded-lg bg-zinc-900 border border-zinc-800">
                      <div className="text-2xl font-bold text-white">156</div>
                      <div className="text-xs text-zinc-400">Detections</div>
                    </div>
                  </div>
                </SettingsSection>
              </div>
            )}

            {activeTab === 'notifications' && (
              <div className="space-y-6">
                <SettingsSection title="Email Notifications" description="Configure email alerts">
                  <ToggleSetting
                    label="Critical detections"
                    description="Get notified when critical issues are detected"
                    defaultChecked
                  />
                  <ToggleSetting
                    label="Daily summary"
                    description="Receive a daily summary of all detections"
                    defaultChecked
                  />
                  <ToggleSetting
                    label="Weekly report"
                    description="Receive a weekly analytics report"
                  />
                </SettingsSection>

                <SettingsSection title="Slack Integration" description="Send notifications to Slack">
                  <SettingsField label="Webhook URL">
                    <Input
                      placeholder="https://hooks.slack.com/services/..."
                    />
                  </SettingsField>
                  <ToggleSetting
                    label="Send to Slack"
                    description="Forward critical alerts to your Slack channel"
                  />
                </SettingsSection>
              </div>
            )}

            {activeTab === 'detection' && (
              <div className="space-y-6">
                <Link
                  href="/settings/tuning"
                  className="flex items-center justify-between p-4 rounded-xl bg-gradient-to-r from-violet-600/10 to-blue-600/10 border border-violet-500/20 hover:border-violet-500/40 transition-colors group"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-violet-600/20 rounded-lg">
                      <Sliders className="w-5 h-5 text-violet-400" />
                    </div>
                    <div>
                      <div className="text-white font-medium">Advanced Threshold Tuning</div>
                      <div className="text-sm text-zinc-400">
                        Optimize detection accuracy using feedback analytics
                      </div>
                    </div>
                  </div>
                  <ExternalLink size={16} className="text-violet-400 group-hover:translate-x-1 transition-transform" />
                </Link>

                <SettingsSection title="Detection Sensitivity" description="Adjust detection thresholds">
                  <SettingsField label="Confidence Threshold (%)">
                    <input
                      type="range"
                      min="50"
                      max="99"
                      defaultValue="75"
                      className="w-full accent-blue-500"
                    />
                    <div className="flex justify-between text-xs text-zinc-500 mt-1">
                      <span>More detections</span>
                      <span>Fewer false positives</span>
                    </div>
                  </SettingsField>

                  <SettingsField label="Loop Detection Methods">
                    <div className="space-y-2">
                      <ToggleSetting label="Structural matching" defaultChecked />
                      <ToggleSetting label="Hash collision detection" defaultChecked />
                      <ToggleSetting label="Semantic clustering" defaultChecked />
                      <ToggleSetting label="Embedding similarity" />
                    </div>
                  </SettingsField>
                </SettingsSection>

                <SettingsSection title="Auto-Actions" description="Automatic responses to detections">
                  <ToggleSetting
                    label="Auto-validate low confidence"
                    description="Automatically mark detections below 60% as false positives"
                  />
                  <ToggleSetting
                    label="Auto-alert on critical"
                    description="Immediately send alerts for critical severity detections"
                    defaultChecked
                  />
                </SettingsSection>
              </div>
            )}

            {activeTab === 'integrations' && (
              <div className="space-y-6">
                <SettingsSection title="OTEL Endpoint" description="Configure your OpenTelemetry endpoint">
                  <div className="p-4 rounded-lg bg-zinc-900 border border-zinc-800">
                    <div className="flex items-center gap-2 mb-2">
                      <Code size={14} className="text-blue-400" />
                      <span className="text-sm font-medium text-white">Endpoint URL</span>
                    </div>
                    <code className="text-sm text-zinc-300 font-mono">
                      https://api.pisama.ai/v1/traces
                    </code>
                  </div>
                </SettingsSection>

                <SettingsSection title="Connected Frameworks" description="Frameworks sending data to PISAMA">
                  <div className="space-y-3">
                    <IntegrationCard
                      name="LangGraph"
                      status="connected"
                      lastSeen="2 minutes ago"
                    />
                    <IntegrationCard
                      name="AutoGen"
                      status="connected"
                      lastSeen="5 minutes ago"
                    />
                    <IntegrationCard
                      name="CrewAI"
                      status="disconnected"
                    />
                    <IntegrationCard
                      name="Custom"
                      status="connected"
                      lastSeen="1 hour ago"
                    />
                  </div>
                </SettingsSection>

                <SettingsSection title="Webhooks" description="Send detection events to external services">
                  <Button variant="secondary" size="sm">
                    <Webhook size={14} className="mr-2" />
                    Add Webhook
                  </Button>
                </SettingsSection>
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  )
}

interface SettingsSectionProps {
  title: string
  description: string
  children: React.ReactNode
}

function SettingsSection({ title, description, children }: SettingsSectionProps) {
  return (
    <div className="p-6 rounded-xl bg-zinc-900/50 border border-zinc-800">
      <h3 className="text-lg font-semibold text-white mb-1">{title}</h3>
      <p className="text-sm text-zinc-400 mb-4">{description}</p>
      <div className="space-y-4">{children}</div>
    </div>
  )
}

interface SettingsFieldProps {
  label: string
  children: React.ReactNode
}

function SettingsField({ label, children }: SettingsFieldProps) {
  return (
    <div>
      <Label className="mb-2 block">{label}</Label>
      {children}
    </div>
  )
}

interface ToggleSettingProps {
  label: string
  description?: string
  defaultChecked?: boolean
}

function ToggleSetting({ label, description, defaultChecked }: ToggleSettingProps) {
  const [checked, setChecked] = useState(defaultChecked || false)

  return (
    <div className="flex items-start gap-3">
      <Switch
        checked={checked}
        onCheckedChange={setChecked}
        className="mt-0.5"
      />
      <div>
        <div className="text-sm font-medium text-white">{label}</div>
        {description && (
          <div className="text-xs text-zinc-400">{description}</div>
        )}
      </div>
    </div>
  )
}

interface IntegrationCardProps {
  name: string
  status: 'connected' | 'disconnected'
  lastSeen?: string
}

function IntegrationCard({ name, status, lastSeen }: IntegrationCardProps) {
  return (
    <div className="flex items-center justify-between p-3 rounded-lg bg-zinc-900 border border-zinc-800">
      <div className="flex items-center gap-3">
        <div className={cn(
          'w-2 h-2 rounded-full',
          status === 'connected' ? 'bg-green-500' : 'bg-zinc-500'
        )} />
        <div>
          <div className="text-sm font-medium text-white">{name}</div>
          {lastSeen && (
            <div className="text-xs text-zinc-400">Last seen: {lastSeen}</div>
          )}
        </div>
      </div>
      <span className={cn(
        'text-xs px-2 py-1 rounded-full',
        status === 'connected'
          ? 'bg-green-500/10 text-green-400'
          : 'bg-zinc-500/10 text-zinc-400'
      )}>
        {status}
      </span>
    </div>
  )
}
