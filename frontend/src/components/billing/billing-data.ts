export const PLAN_TIERS = ['free', 'pro', 'team', 'enterprise'] as const
export type PlanTier = (typeof PLAN_TIERS)[number]

export interface PlanDisplayData {
  slug: PlanTier
  name: string
  monthlyPrice: number | null
  annualMonthlyPrice: number | null
  priceNote: string
  tagline: string
  features: string[]
}

export const planDisplayData: PlanDisplayData[] = [
  {
    slug: 'free',
    name: 'Free',
    monthlyPrice: 0,
    annualMonthlyPrice: null,
    priceNote: 'forever',
    tagline: 'For getting started',
    features: [
      '1 project',
      '100 daily runs',
      'Core detectors',
      'Basic fix suggestions',
      '7-day retention',
      'Community support',
    ],
  },
  {
    slug: 'pro',
    name: 'Pro',
    monthlyPrice: 29,
    annualMonthlyPrice: 24,
    priceNote: '/mo',
    tagline: 'For individual developers',
    features: [
      '10 projects',
      '5,000 daily runs',
      'All detectors',
      'API access',
      'Webhooks & Slack alerts',
      '30-day retention',
      'Email support',
    ],
  },
  {
    slug: 'team',
    name: 'Team',
    monthlyPrice: 79,
    annualMonthlyPrice: 66,
    priceNote: '/mo',
    tagline: 'For growing teams',
    features: [
      '50 projects',
      '25,000 daily runs',
      'All detectors + ML tier',
      '5 team members',
      'SSO & RBAC',
      'Custom webhooks',
      '90-day retention',
      'Priority support',
    ],
  },
  {
    slug: 'enterprise',
    name: 'Enterprise',
    monthlyPrice: null,
    annualMonthlyPrice: null,
    priceNote: '',
    tagline: 'For organizations at scale',
    features: [
      'Unlimited projects',
      'Unlimited runs',
      'All detectors + ML + custom',
      'Unlimited team',
      'Self-healing automation',
      'SSO & RBAC',
      'SLA guarantee',
      'Dedicated support',
      'On-prem option',
    ],
  },
]

// ---------------------------------------------------------------------------
// Feature comparison table data
// ---------------------------------------------------------------------------

export interface ComparisonRow {
  feature: string
  free: string | boolean
  pro: string | boolean
  team: string | boolean
  enterprise: string | boolean
}

export interface ComparisonCategory {
  name: string
  rows: ComparisonRow[]
}

export const comparisonCategories: ComparisonCategory[] = [
  {
    name: 'Usage Limits',
    rows: [
      { feature: 'Projects', free: '1', pro: '10', team: '50', enterprise: 'Unlimited' },
      { feature: 'Daily runs', free: '100', pro: '5,000', team: '25,000', enterprise: 'Unlimited' },
      { feature: 'Data retention', free: '7 days', pro: '30 days', team: '90 days', enterprise: 'Custom' },
      { feature: 'API rate limit', free: '30/min', pro: '200/min', team: '1,000/min', enterprise: '10,000/min' },
    ],
  },
  {
    name: 'Detection',
    rows: [
      { feature: 'Core detectors', free: true, pro: true, team: true, enterprise: true },
      { feature: 'ML-powered detection', free: false, pro: true, team: true, enterprise: true },
      { feature: 'Custom detectors', free: false, pro: false, team: false, enterprise: true },
      { feature: 'Fix suggestions', free: 'Basic', pro: 'Code-level', team: 'Code-level', enterprise: 'Code-level + custom' },
    ],
  },
  {
    name: 'Integrations',
    rows: [
      { feature: 'API access', free: false, pro: true, team: true, enterprise: true },
      { feature: 'Webhooks', free: false, pro: true, team: true, enterprise: true },
      { feature: 'Slack alerts', free: false, pro: true, team: true, enterprise: true },
      { feature: 'SSO', free: false, pro: false, team: true, enterprise: true },
      { feature: 'Custom integrations', free: false, pro: false, team: false, enterprise: true },
    ],
  },
  {
    name: 'Support',
    rows: [
      { feature: 'Community support', free: true, pro: true, team: true, enterprise: true },
      { feature: 'Email support', free: false, pro: true, team: true, enterprise: true },
      { feature: 'Priority support', free: false, pro: false, team: true, enterprise: true },
      { feature: 'Dedicated support', free: false, pro: false, team: false, enterprise: true },
      { feature: 'SLA guarantee', free: false, pro: false, team: false, enterprise: true },
    ],
  },
  {
    name: 'Team & Admin',
    rows: [
      { feature: 'Team members', free: '1', pro: '1', team: '5', enterprise: 'Unlimited' },
      { feature: 'RBAC', free: false, pro: false, team: true, enterprise: true },
      { feature: 'Audit logs', free: false, pro: false, team: true, enterprise: true },
      { feature: 'Self-healing automation', free: false, pro: false, team: false, enterprise: true },
    ],
  },
]
