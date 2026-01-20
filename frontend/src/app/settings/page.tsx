'use client'

export const dynamic = 'force-dynamic'

import { useState } from 'react'
import { Layout } from '@/components/common/Layout'
import { clsx } from 'clsx'
import {
  Settings,
  Key,
  Bell,
  Shield,
  Database,
  Webhook,
  Code,
  Save,
  Copy,
  Eye,
  EyeOff,
  Check,
  AlertTriangle,
  Zap,
  RefreshCw,
  Trash2,
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
            <p className="text-sm text-slate-400">
              Configure your PISAMA preferences
            </p>
          </div>
          <button
            onClick={handleSave}
            className={clsx(
              'flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all',
              saved
                ? 'bg-emerald-600 text-white'
                : 'bg-primary-600 hover:bg-primary-700 text-white'
            )}
          >
            {saved ? <Check size={16} /> : <Save size={16} />}
            {saved ? 'Saved!' : 'Save Changes'}
          </button>
        </div>

        <div className="flex gap-6">
          <div className="w-48 flex-shrink-0">
            <nav className="space-y-1">
              {tabs.map((tab) => {
                const Icon = tab.icon
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={clsx(
                      'w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                      activeTab === tab.id
                        ? 'bg-primary-600 text-white'
                        : 'text-slate-400 hover:text-white hover:bg-slate-800'
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
                    <input
                      type="text"
                      defaultValue="My Workspace"
                      className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white focus:outline-none focus:border-primary-500"
                    />
                  </SettingsField>
                  <SettingsField label="Timezone">
                    <select className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white focus:outline-none focus:border-primary-500">
                      <option>UTC</option>
                      <option>America/New_York</option>
                      <option>America/Los_Angeles</option>
                      <option>Europe/London</option>
                      <option>Europe/Helsinki</option>
                      <option>Asia/Tokyo</option>
                    </select>
                  </SettingsField>
                </SettingsSection>

                <SettingsSection title="Data Retention" description="Configure how long data is stored">
                  <SettingsField label="Trace Retention (days)">
                    <input
                      type="number"
                      defaultValue={30}
                      className="w-32 px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white focus:outline-none focus:border-primary-500"
                    />
                  </SettingsField>
                  <SettingsField label="Detection Retention (days)">
                    <input
                      type="number"
                      defaultValue={90}
                      className="w-32 px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white focus:outline-none focus:border-primary-500"
                    />
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
                          className={clsx(
                            'flex-1 p-3 rounded-lg border-2 transition-all text-left',
                            preferences.userType === 'n8n_user'
                              ? 'border-primary-500 bg-primary-500/10'
                              : 'border-slate-700 hover:border-slate-600'
                          )}
                        >
                          <div className="text-sm font-medium text-white">n8n / Workflows</div>
                          <div className="text-xs text-slate-400">Simplified, visual interface</div>
                        </button>
                        <button
                          onClick={() => setUserType('developer')}
                          className={clsx(
                            'flex-1 p-3 rounded-lg border-2 transition-all text-left',
                            preferences.userType === 'developer'
                              ? 'border-primary-500 bg-primary-500/10'
                              : 'border-slate-700 hover:border-slate-600'
                          )}
                        >
                          <div className="text-sm font-medium text-white">Developer</div>
                          <div className="text-xs text-slate-400">Full-featured, technical</div>
                        </button>
                      </div>
                    </SettingsField>

                    {isN8nUser && (
                      <div className="p-4 rounded-lg bg-slate-900 border border-slate-700">
                        <label className="flex items-start gap-3 cursor-pointer">
                          <div className="relative mt-1">
                            <input
                              type="checkbox"
                              checked={preferences.developerMode}
                              onChange={(e) => setDeveloperMode(e.target.checked)}
                              className="sr-only"
                            />
                            <div
                              className={clsx(
                                'w-10 h-6 rounded-full transition-colors',
                                preferences.developerMode ? 'bg-primary-600' : 'bg-slate-700'
                              )}
                            />
                            <div
                              className={clsx(
                                'absolute top-1 w-4 h-4 rounded-full bg-white transition-transform',
                                preferences.developerMode ? 'translate-x-5' : 'translate-x-1'
                              )}
                            />
                          </div>
                          <div>
                            <div className="text-sm font-medium text-white flex items-center gap-2">
                              <Code2 size={16} />
                              Developer Mode
                            </div>
                            <div className="text-xs text-slate-400">
                              Show advanced features like Traces, Agents, and raw data views.
                              Turn this on if you want access to technical debugging tools.
                            </div>
                          </div>
                        </label>
                      </div>
                    )}
                  </div>
                </SettingsSection>
              </div>
            )}

            {activeTab === 'api' && (
              <div className="space-y-6">
                <SettingsSection title="API Key" description="Use this key to authenticate with the PISAMA API">
                  <div className="p-4 rounded-lg bg-slate-900 border border-slate-700">
                    <div className="flex items-center gap-3">
                      <div className="flex-1 font-mono text-sm text-slate-300">
                        {showApiKey ? 'mao_sk_1234567890abcdefghijklmnop' : '••••••••••••••••••••••••••••••'}
                      </div>
                      <button
                        onClick={() => setShowApiKey(!showApiKey)}
                        className="p-2 text-slate-400 hover:text-white transition-colors"
                      >
                        {showApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                      <button
                        onClick={() => navigator.clipboard.writeText('mao_sk_1234567890abcdefghijklmnop')}
                        className="p-2 text-slate-400 hover:text-white transition-colors"
                      >
                        <Copy size={16} />
                      </button>
                    </div>
                  </div>
                  <div className="flex gap-3 mt-4">
                    <button className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-white text-sm transition-colors">
                      <RefreshCw size={14} />
                      Regenerate Key
                    </button>
                  </div>
                </SettingsSection>

                <SettingsSection title="Usage" description="API usage for current billing period">
                  <div className="grid grid-cols-3 gap-4">
                    <div className="p-4 rounded-lg bg-slate-900 border border-slate-700">
                      <div className="text-2xl font-bold text-white">12,450</div>
                      <div className="text-xs text-slate-400">API Calls</div>
                    </div>
                    <div className="p-4 rounded-lg bg-slate-900 border border-slate-700">
                      <div className="text-2xl font-bold text-white">847</div>
                      <div className="text-xs text-slate-400">Traces Processed</div>
                    </div>
                    <div className="p-4 rounded-lg bg-slate-900 border border-slate-700">
                      <div className="text-2xl font-bold text-white">156</div>
                      <div className="text-xs text-slate-400">Detections</div>
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
                    <input
                      type="text"
                      placeholder="https://hooks.slack.com/services/..."
                      className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white placeholder-slate-500 focus:outline-none focus:border-primary-500"
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
                {/* Link to advanced threshold tuning */}
                <Link
                  href="/settings/tuning"
                  className="flex items-center justify-between p-4 rounded-xl bg-gradient-to-r from-purple-600/20 to-indigo-600/20 border border-purple-500/30 hover:border-purple-500/50 transition-colors group"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-purple-600/30 rounded-lg">
                      <Sliders className="w-5 h-5 text-purple-400" />
                    </div>
                    <div>
                      <div className="text-white font-medium">Advanced Threshold Tuning</div>
                      <div className="text-sm text-slate-400">
                        Optimize detection accuracy using feedback analytics
                      </div>
                    </div>
                  </div>
                  <ExternalLink size={16} className="text-purple-400 group-hover:translate-x-1 transition-transform" />
                </Link>

                <SettingsSection title="Detection Sensitivity" description="Adjust detection thresholds">
                  <SettingsField label="Confidence Threshold (%)">
                    <input
                      type="range"
                      min="50"
                      max="99"
                      defaultValue="75"
                      className="w-full"
                    />
                    <div className="flex justify-between text-xs text-slate-400 mt-1">
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
                  <div className="p-4 rounded-lg bg-slate-900 border border-slate-700">
                    <div className="flex items-center gap-2 mb-2">
                      <Code size={14} className="text-primary-400" />
                      <span className="text-sm font-medium text-white">Endpoint URL</span>
                    </div>
                    <code className="text-sm text-slate-300">
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
                  <button className="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-white text-sm transition-colors">
                    <Webhook size={14} />
                    Add Webhook
                  </button>
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
    <div className="p-6 rounded-xl bg-slate-800/50 border border-slate-700">
      <h3 className="text-lg font-semibold text-white mb-1">{title}</h3>
      <p className="text-sm text-slate-400 mb-4">{description}</p>
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
      <label className="text-sm text-slate-300 mb-2 block">{label}</label>
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
    <label className="flex items-start gap-3 cursor-pointer">
      <div className="relative mt-1">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => setChecked(e.target.checked)}
          className="sr-only"
        />
        <div
          className={clsx(
            'w-10 h-6 rounded-full transition-colors',
            checked ? 'bg-primary-600' : 'bg-slate-700'
          )}
        />
        <div
          className={clsx(
            'absolute top-1 w-4 h-4 rounded-full bg-white transition-transform',
            checked ? 'translate-x-5' : 'translate-x-1'
          )}
        />
      </div>
      <div>
        <div className="text-sm font-medium text-white">{label}</div>
        {description && (
          <div className="text-xs text-slate-400">{description}</div>
        )}
      </div>
    </label>
  )
}

interface IntegrationCardProps {
  name: string
  status: 'connected' | 'disconnected'
  lastSeen?: string
}

function IntegrationCard({ name, status, lastSeen }: IntegrationCardProps) {
  return (
    <div className="flex items-center justify-between p-3 rounded-lg bg-slate-900 border border-slate-700">
      <div className="flex items-center gap-3">
        <div className={clsx(
          'w-2 h-2 rounded-full',
          status === 'connected' ? 'bg-emerald-500' : 'bg-slate-500'
        )} />
        <div>
          <div className="text-sm font-medium text-white">{name}</div>
          {lastSeen && (
            <div className="text-xs text-slate-400">Last seen: {lastSeen}</div>
          )}
        </div>
      </div>
      <span className={clsx(
        'text-xs px-2 py-1 rounded-full',
        status === 'connected'
          ? 'bg-emerald-500/20 text-emerald-400'
          : 'bg-slate-500/20 text-slate-400'
      )}>
        {status}
      </span>
    </div>
  )
}
