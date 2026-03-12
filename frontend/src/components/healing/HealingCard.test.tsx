import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { HealingCard } from './HealingCard'
import type { HealingRecord } from '@/lib/api'

// Mock the PipelineStepper since it's a child component with its own rendering logic
vi.mock('./PipelineStepper', () => ({
  PipelineStepper: ({ healing }: { healing: HealingRecord }) => (
    <div data-testid="pipeline-stepper">Pipeline for {healing.id}</div>
  ),
}))

function makeHealing(overrides: Partial<HealingRecord> = {}): HealingRecord {
  return {
    id: 'heal-001',
    detection_id: 'det-abcdef1234567890',
    status: 'staged',
    fix_type: 'prompt_update',
    fix_id: 'fix-001',
    fix_suggestions: [],
    applied_fixes: {},
    original_state: {},
    rollback_available: false,
    validation_status: null,
    validation_results: {},
    approval_required: false,
    approved_by: null,
    approved_at: null,
    started_at: null,
    completed_at: null,
    rolled_back_at: null,
    created_at: new Date().toISOString(),
    error_message: null,
    ...overrides,
  }
}

describe('HealingCard', () => {
  it('renders the fix type as header text', () => {
    render(<HealingCard healing={makeHealing({ fix_type: 'prompt_update' })} />)
    expect(screen.getByText('prompt update')).toBeInTheDocument()
  })

  it('shows the detection ID (truncated)', () => {
    render(<HealingCard healing={makeHealing()} />)
    expect(screen.getByText(/det-abcd/)).toBeInTheDocument()
  })

  it('renders the status badge', () => {
    render(<HealingCard healing={makeHealing({ status: 'staged' })} />)
    expect(screen.getByText('Ready to test')).toBeInTheDocument()
  })

  it('renders applied status badge', () => {
    render(<HealingCard healing={makeHealing({ status: 'applied' })} />)
    expect(screen.getByText('Fixed!')).toBeInTheDocument()
  })

  it('renders failed status badge', () => {
    render(<HealingCard healing={makeHealing({ status: 'failed' })} />)
    expect(screen.getByText("Couldn't fix")).toBeInTheDocument()
  })

  it('shows Awaiting Approval badge when approval is required and status is pending', () => {
    render(<HealingCard healing={makeHealing({ status: 'pending', approval_required: true })} />)
    expect(screen.getByText('Awaiting Approval')).toBeInTheDocument()
  })

  it('does not show Awaiting Approval when not required', () => {
    render(<HealingCard healing={makeHealing({ status: 'pending', approval_required: false })} />)
    expect(screen.queryByText('Awaiting Approval')).not.toBeInTheDocument()
  })

  it('does not show Awaiting Approval when status is not pending', () => {
    render(<HealingCard healing={makeHealing({ status: 'applied', approval_required: true })} />)
    expect(screen.queryByText('Awaiting Approval')).not.toBeInTheDocument()
  })

  it('starts collapsed by default', () => {
    render(<HealingCard healing={makeHealing()} />)
    expect(screen.queryByTestId('pipeline-stepper')).not.toBeInTheDocument()
  })

  it('starts expanded when isExpanded prop is true', () => {
    render(<HealingCard healing={makeHealing()} isExpanded />)
    expect(screen.getByTestId('pipeline-stepper')).toBeInTheDocument()
  })

  it('toggles expansion on header click', async () => {
    const user = userEvent.setup()
    render(<HealingCard healing={makeHealing()} />)

    // Click to expand
    await user.click(screen.getByText('prompt update'))
    expect(screen.getByTestId('pipeline-stepper')).toBeInTheDocument()

    // Click to collapse
    await user.click(screen.getByText('prompt update'))
    expect(screen.queryByTestId('pipeline-stepper')).not.toBeInTheDocument()
  })

  it('shows promote and reject buttons for staged healing when expanded', async () => {
    const _user = userEvent.setup()
    const onPromote = vi.fn()
    const onReject = vi.fn()
    render(
      <HealingCard
        healing={makeHealing({ status: 'staged', validation_status: 'passed' })}
        onPromote={onPromote}
        onReject={onReject}
        isExpanded
      />
    )

    expect(screen.getByText('Make it Live')).toBeInTheDocument()
    expect(screen.getByText("Don't Apply")).toBeInTheDocument()
  })

  it('disables promote button when fix is not verified', () => {
    render(
      <HealingCard
        healing={makeHealing({ status: 'staged', validation_status: null })}
        onPromote={vi.fn()}
        onReject={vi.fn()}
        isExpanded
      />
    )

    const promoteBtn = screen.getByText('Make it Live').closest('button')
    expect(promoteBtn).toBeDisabled()
  })

  it('enables promote button when fix is verified', () => {
    render(
      <HealingCard
        healing={makeHealing({ status: 'staged', validation_status: 'passed' })}
        onPromote={vi.fn()}
        onReject={vi.fn()}
        isExpanded
      />
    )

    const promoteBtn = screen.getByText('Make it Live').closest('button')
    expect(promoteBtn).not.toBeDisabled()
  })

  it('calls onPromote when promote button is clicked', async () => {
    const user = userEvent.setup()
    const onPromote = vi.fn().mockResolvedValue(undefined)
    render(
      <HealingCard
        healing={makeHealing({ status: 'staged', validation_status: 'passed' })}
        onPromote={onPromote}
        onReject={vi.fn()}
        isExpanded
      />
    )

    await user.click(screen.getByText('Make it Live'))
    expect(onPromote).toHaveBeenCalledTimes(1)
    expect(onPromote.mock.calls[0][0]).toBe('heal-001')
  })

  it('calls onReject when reject button is clicked', async () => {
    const user = userEvent.setup()
    const onReject = vi.fn().mockResolvedValue(undefined)
    render(
      <HealingCard
        healing={makeHealing({ status: 'staged' })}
        onPromote={vi.fn()}
        onReject={onReject}
        isExpanded
      />
    )

    await user.click(screen.getByText("Don't Apply"))
    expect(onReject).toHaveBeenCalledTimes(1)
    expect(onReject.mock.calls[0][0]).toBe('heal-001')
  })

  it('shows rollback button for applied healing with rollback available', () => {
    render(
      <HealingCard
        healing={makeHealing({ status: 'applied', rollback_available: true })}
        onRollback={vi.fn()}
        isExpanded
      />
    )

    expect(screen.getByText('Undo This Fix')).toBeInTheDocument()
  })

  it('does not show rollback button when rollback is not available', () => {
    render(
      <HealingCard
        healing={makeHealing({ status: 'applied', rollback_available: false })}
        onRollback={vi.fn()}
        isExpanded
      />
    )

    expect(screen.queryByText('Undo This Fix')).not.toBeInTheDocument()
  })

  it('calls onRollback when rollback button is clicked', async () => {
    const user = userEvent.setup()
    const onRollback = vi.fn().mockResolvedValue(undefined)
    render(
      <HealingCard
        healing={makeHealing({ status: 'applied', rollback_available: true })}
        onRollback={onRollback}
        isExpanded
      />
    )

    await user.click(screen.getByText('Undo This Fix'))
    expect(onRollback).toHaveBeenCalledTimes(1)
    expect(onRollback.mock.calls[0][0]).toBe('heal-001')
  })

  it('shows error message when present', () => {
    render(
      <HealingCard
        healing={makeHealing({ error_message: 'Something broke badly' })}
        isExpanded
      />
    )

    expect(screen.getByText('Something broke badly')).toBeInTheDocument()
    expect(screen.getByText('What Went Wrong')).toBeInTheDocument()
  })

  it('does not show error section when no error', () => {
    render(
      <HealingCard healing={makeHealing({ error_message: null })} isExpanded />
    )

    expect(screen.queryByText('What Went Wrong')).not.toBeInTheDocument()
  })

  it('shows Verified badge when validation passed', () => {
    render(
      <HealingCard healing={makeHealing({ validation_status: 'passed' })} />
    )

    expect(screen.getByText('Verified')).toBeInTheDocument()
  })

  it('shows Unverified badge when validation failed', () => {
    render(
      <HealingCard healing={makeHealing({ validation_status: 'failed' })} />
    )

    expect(screen.getByText('Unverified')).toBeInTheDocument()
  })

  it('shows verify button when onVerify is provided and healing is staged', () => {
    render(
      <HealingCard
        healing={makeHealing({ status: 'staged' })}
        onVerify={vi.fn()}
        onPromote={vi.fn()}
        onReject={vi.fn()}
        isExpanded
      />
    )

    expect(screen.getByText('Verify Fix')).toBeInTheDocument()
  })

  it('calls onVerify with level 1 when verify button is clicked', async () => {
    const user = userEvent.setup()
    const onVerify = vi.fn().mockResolvedValue(undefined)
    render(
      <HealingCard
        healing={makeHealing({ status: 'staged' })}
        onVerify={onVerify}
        onPromote={vi.fn()}
        onReject={vi.fn()}
        isExpanded
      />
    )

    await user.click(screen.getByText('Verify Fix'))
    expect(onVerify).toHaveBeenCalledWith('heal-001', 1)
  })

  it('shows deployment stage label when present', () => {
    render(
      <HealingCard
        healing={makeHealing({ deployment_stage: 'promoted' })}
      />
    )

    expect(screen.getByText('Live')).toBeInTheDocument()
  })

  it('shows fix suggestions when expanded', () => {
    render(
      <HealingCard
        healing={makeHealing({
          fix_suggestions: [
            { id: 's1', fix_type: 'prompt', confidence: 'HIGH', description: 'Update the system prompt', title: 'Fix Prompt' },
          ],
        })}
        isExpanded
      />
    )

    expect(screen.getByText('Fix Prompt')).toBeInTheDocument()
    expect(screen.getByText('Update the system prompt')).toBeInTheDocument()
  })

  it('shows View Problem button when expanded', () => {
    render(<HealingCard healing={makeHealing()} isExpanded />)
    expect(screen.getByText('View Problem')).toBeInTheDocument()
  })

  it('shows approval info when approval is required and expanded', () => {
    render(
      <HealingCard
        healing={makeHealing({
          approval_required: true,
          approved_by: 'admin@test.com',
        })}
        isExpanded
      />
    )

    expect(screen.getByText('Approval Info')).toBeInTheDocument()
    expect(screen.getByText('admin@test.com')).toBeInTheDocument()
  })
})
