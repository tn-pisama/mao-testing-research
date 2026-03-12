import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { FailureCard } from './FailureCard'
import type { Detection } from '@/lib/api'

// Mock FixPreviewModal since it has its own complex rendering
vi.mock('../healing/FixPreviewModal', () => ({
  FixPreviewModal: ({ isOpen }: { isOpen: boolean }) =>
    isOpen ? <div data-testid="fix-preview-modal">Fix Preview</div> : null,
}))

// Mock the Tooltip helpers to render plainly
vi.mock('../ui/Tooltip', () => ({
  TermTooltip: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
  getPlainEnglishTitle: (type: string) => {
    const map: Record<string, string> = {
      infinite_loop: 'Workflow Running Forever',
      state_corruption: 'Data Got Scrambled',
      hallucination: 'AI Made Something Up',
    }
    return map[type] || type.replace(/_/g, ' ')
  },
}))

function makeDetection(overrides: Partial<Detection> = {}): Detection {
  return {
    id: 'det-001',
    trace_id: 'trace-abcdef1234567890',
    detection_type: 'infinite_loop',
    confidence: 92,
    method: 'hash_comparison',
    details: { severity: 'critical' },
    validated: true,
    created_at: new Date().toISOString(),
    confidence_tier: 'HIGH',
    ...overrides,
  }
}

describe('FailureCard', () => {
  it('renders the detection type as plain English title', () => {
    render(<FailureCard detection={makeDetection()} />)
    expect(screen.getByText('Workflow Running Forever')).toBeInTheDocument()
  })

  it('shows the trace ID (truncated)', () => {
    render(<FailureCard detection={makeDetection()} />)
    expect(screen.getByText(/trace-ab/)).toBeInTheDocument()
  })

  it('shows severity badge for critical', () => {
    render(<FailureCard detection={makeDetection({ details: { severity: 'critical' } })} />)
    expect(screen.getByText('Critical')).toBeInTheDocument()
  })

  it('shows severity badge for high', () => {
    render(<FailureCard detection={makeDetection({ details: { severity: 'high' } })} />)
    expect(screen.getByText('High')).toBeInTheDocument()
  })

  it('shows severity badge for medium', () => {
    render(<FailureCard detection={makeDetection({ details: { severity: 'medium' } })} />)
    expect(screen.getByText('Medium')).toBeInTheDocument()
  })

  it('shows severity badge for low', () => {
    render(<FailureCard detection={makeDetection({ details: { severity: 'low' } })} />)
    expect(screen.getByText('Low')).toBeInTheDocument()
  })

  it('defaults to medium severity when not specified', () => {
    render(<FailureCard detection={makeDetection({ details: {} })} />)
    expect(screen.getByText('Medium')).toBeInTheDocument()
  })

  it('shows confidence percentage', () => {
    render(<FailureCard detection={makeDetection({ confidence: 92 })} />)
    expect(screen.getByText('92% certain')).toBeInTheDocument()
  })

  it('starts collapsed', () => {
    render(<FailureCard detection={makeDetection({ business_impact: 'Workflows will fail' })} />)
    expect(screen.queryByText('Why This Matters')).not.toBeInTheDocument()
  })

  it('expands on header click', async () => {
    const user = userEvent.setup()
    render(<FailureCard detection={makeDetection({ business_impact: 'Workflows will fail' })} />)

    await user.click(screen.getByText('Workflow Running Forever'))
    expect(screen.getByText('Why This Matters')).toBeInTheDocument()
    expect(screen.getByText('Workflows will fail')).toBeInTheDocument()
  })

  it('shows business impact when expanded', async () => {
    const user = userEvent.setup()
    render(<FailureCard detection={makeDetection({ business_impact: 'Customer data may be lost' })} />)

    await user.click(screen.getByText('Workflow Running Forever'))
    expect(screen.getByText('Customer data may be lost')).toBeInTheDocument()
  })

  it('shows suggested action when expanded', async () => {
    const user = userEvent.setup()
    render(<FailureCard detection={makeDetection({ suggested_action: 'Add a loop counter' })} />)

    await user.click(screen.getByText('Workflow Running Forever'))
    expect(screen.getByText('What You Can Do')).toBeInTheDocument()
    expect(screen.getByText('Add a loop counter')).toBeInTheDocument()
  })

  it('shows explanation when expanded', async () => {
    const user = userEvent.setup()
    render(<FailureCard detection={makeDetection({ explanation: 'The workflow repeated 50 times' })} />)

    await user.click(screen.getByText('Workflow Running Forever'))
    expect(screen.getByText('What Happened')).toBeInTheDocument()
    expect(screen.getByText('The workflow repeated 50 times')).toBeInTheDocument()
  })

  it('shows Generate Fix button when onGenerateFix is provided', async () => {
    const user = userEvent.setup()
    render(<FailureCard detection={makeDetection()} onGenerateFix={vi.fn()} />)

    await user.click(screen.getByText('Workflow Running Forever'))
    expect(screen.getByText('Generate Fix')).toBeInTheDocument()
  })

  it('does not show Generate Fix button when onGenerateFix is not provided', async () => {
    const user = userEvent.setup()
    render(<FailureCard detection={makeDetection()} />)

    await user.click(screen.getByText('Workflow Running Forever'))
    expect(screen.queryByText('Generate Fix')).not.toBeInTheDocument()
  })

  it('calls onGenerateFix and opens preview modal', async () => {
    const user = userEvent.setup()
    const onGenerateFix = vi.fn().mockResolvedValue({
      fix: { type: 'prompt', description: 'Fix description', confidence: 'HIGH' },
      diff: { before: '{}', after: '{}' },
    })
    render(<FailureCard detection={makeDetection()} onGenerateFix={onGenerateFix} />)

    await user.click(screen.getByText('Workflow Running Forever'))
    await user.click(screen.getByText('Generate Fix'))

    expect(onGenerateFix).toHaveBeenCalledWith('det-001')
    expect(screen.getByTestId('fix-preview-modal')).toBeInTheDocument()
  })

  it('shows View Workflow Run button when expanded', async () => {
    const user = userEvent.setup()
    render(<FailureCard detection={makeDetection()} />)

    await user.click(screen.getByText('Workflow Running Forever'))
    expect(screen.getByText('View Workflow Run')).toBeInTheDocument()
  })

  it('shows detection method in subtitle', () => {
    render(<FailureCard detection={makeDetection({ method: 'hash_comparison' })} />)
    expect(screen.getByText(/detected by hash comparison/)).toBeInTheDocument()
  })

  it('collapses on second header click', async () => {
    const user = userEvent.setup()
    render(<FailureCard detection={makeDetection({ business_impact: 'Test impact' })} />)

    await user.click(screen.getByText('Workflow Running Forever'))
    expect(screen.getByText('Test impact')).toBeInTheDocument()

    await user.click(screen.getByText('Workflow Running Forever'))
    expect(screen.queryByText('Test impact')).not.toBeInTheDocument()
  })
})
