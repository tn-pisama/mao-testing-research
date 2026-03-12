import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { WorkflowDataTable } from './WorkflowDataTable'
import type { QualityAssessment } from '@/lib/api'

// Mock QualityGradeBadge to render simply
vi.mock('@/components/quality/QualityGradeBadge', () => ({
  QualityGradeBadge: ({ grade }: { grade: string }) => (
    <span data-testid="grade-badge">{grade}</span>
  ),
}))

function makeWorkflow(overrides: Partial<QualityAssessment> = {}): QualityAssessment {
  return {
    id: 'qa-001',
    workflow_id: 'wf-abcdef1234567890',
    workflow_name: 'Test Workflow',
    overall_score: 85,
    overall_grade: 'Good',
    agent_quality_score: 0.88,
    orchestration_quality_score: 0.82,
    agent_scores: [
      { agent_id: 'a1', overall_score: 0.9, dimensions: {}, issues: [] } as any,
      { agent_id: 'a2', overall_score: 0.85, dimensions: {}, issues: [] } as any,
    ],
    orchestration_score: {
      overall_score: 0.82,
      detected_pattern: 'sequential',
      dimensions: {},
      issues: [],
    } as any,
    improvements: [],
    total_issues: 3,
    critical_issues_count: 1,
    source: 'automated',
    created_at: new Date().toISOString(),
    assessed_at: new Date().toISOString(),
    ...overrides,
  }
}

describe('WorkflowDataTable', () => {
  const defaultProps = {
    onSelectWorkflow: vi.fn(),
    selectedWorkflowId: null,
  }

  it('renders column headers', () => {
    render(<WorkflowDataTable workflows={[makeWorkflow()]} {...defaultProps} />)

    expect(screen.getByText('Workflow Name')).toBeInTheDocument()
    expect(screen.getByText('Grade')).toBeInTheDocument()
    expect(screen.getByText('Score')).toBeInTheDocument()
    expect(screen.getByText('Critical')).toBeInTheDocument()
    expect(screen.getByText('Issues')).toBeInTheDocument()
  })

  it('renders workflow data in rows', () => {
    render(<WorkflowDataTable workflows={[makeWorkflow()]} {...defaultProps} />)

    expect(screen.getByText('Test Workflow')).toBeInTheDocument()
    expect(screen.getByText('85%')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('shows "No workflows found" when empty', () => {
    render(<WorkflowDataTable workflows={[]} {...defaultProps} />)
    expect(screen.getByText('No workflows found')).toBeInTheDocument()
  })

  it('shows count in footer', () => {
    const workflows = [
      makeWorkflow({ id: 'qa-001', workflow_name: 'Workflow 1' }),
      makeWorkflow({ id: 'qa-002', workflow_name: 'Workflow 2' }),
    ]
    render(<WorkflowDataTable workflows={workflows} {...defaultProps} />)
    expect(screen.getByText(/Showing 2 workflows/)).toBeInTheDocument()
  })

  it('shows singular "workflow" for single item', () => {
    render(<WorkflowDataTable workflows={[makeWorkflow()]} {...defaultProps} />)
    expect(screen.getByText(/Showing 1 workflow$/)).toBeInTheDocument()
  })

  it('calls onSelectWorkflow when a row is clicked', async () => {
    const user = userEvent.setup()
    const onSelectWorkflow = vi.fn()
    render(
      <WorkflowDataTable
        workflows={[makeWorkflow()]}
        onSelectWorkflow={onSelectWorkflow}
        selectedWorkflowId={null}
      />
    )

    await user.click(screen.getByText('Test Workflow'))
    expect(onSelectWorkflow).toHaveBeenCalledWith('wf-abcdef1234567890')
  })

  it('highlights selected workflow row', () => {
    const { container } = render(
      <WorkflowDataTable
        workflows={[makeWorkflow()]}
        onSelectWorkflow={vi.fn()}
        selectedWorkflowId="wf-abcdef1234567890"
      />
    )

    // The selected row should have the blue highlight class
    const rows = container.querySelectorAll('tbody tr')
    expect(rows[0].className).toContain('bg-blue-500/10')
  })

  it('does not highlight non-selected rows', () => {
    const { container } = render(
      <WorkflowDataTable
        workflows={[makeWorkflow()]}
        onSelectWorkflow={vi.fn()}
        selectedWorkflowId="some-other-id"
      />
    )

    const rows = container.querySelectorAll('tbody tr')
    expect(rows[0].className).not.toContain('bg-blue-500/10')
  })

  it('sorts by column when header is clicked', async () => {
    const user = userEvent.setup()
    const workflows = [
      makeWorkflow({ id: 'qa-001', workflow_name: 'Alpha', overall_score: 60 }),
      makeWorkflow({ id: 'qa-002', workflow_name: 'Beta', overall_score: 90 }),
    ]
    render(<WorkflowDataTable workflows={workflows} {...defaultProps} />)

    // Click "Workflow Name" to sort ascending
    await user.click(screen.getByText('Workflow Name'))

    // Footer should indicate sorting
    expect(screen.getByText(/Sorted by Workflow Name/)).toBeInTheDocument()
  })

  it('cycles sort direction: asc -> desc -> none', async () => {
    const user = userEvent.setup()
    render(<WorkflowDataTable workflows={[makeWorkflow()]} {...defaultProps} />)

    const sortButton = screen.getByText('Workflow Name')

    // First click: asc
    await user.click(sortButton)
    expect(screen.getByText(/ascending/)).toBeInTheDocument()

    // Second click: desc
    await user.click(sortButton)
    expect(screen.getByText(/descending/)).toBeInTheDocument()

    // Third click: no sort
    await user.click(sortButton)
    expect(screen.queryByText(/ascending|descending/)).not.toBeInTheDocument()
  })

  it('opens column visibility control', async () => {
    const user = userEvent.setup()
    render(<WorkflowDataTable workflows={[makeWorkflow()]} {...defaultProps} />)

    await user.click(screen.getByText('Columns'))
    expect(screen.getByText('Column Visibility')).toBeInTheDocument()
    expect(screen.getByText('Show All')).toBeInTheDocument()
    expect(screen.getByText('Reset')).toBeInTheDocument()
  })

  it('toggles column visibility', async () => {
    const user = userEvent.setup()
    render(<WorkflowDataTable workflows={[makeWorkflow()]} {...defaultProps} />)

    // Open column control
    await user.click(screen.getByText('Columns'))

    // The Issues column should have a checkbox
    const issuesCheckbox = screen.getByRole('checkbox', { name: /issues/i })
    expect(issuesCheckbox).toBeChecked()

    // Uncheck it to hide the column
    await user.click(issuesCheckbox)

    // The "Issues" header should be gone from the table
    const table = screen.getByRole('table')
    expect(within(table).queryByText('Issues')).not.toBeInTheDocument()
  })

  it('shows agent count', () => {
    render(<WorkflowDataTable workflows={[makeWorkflow()]} {...defaultProps} />)
    // The workflow has 2 agents in agent_scores
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('shows critical issues with badge when > 0', () => {
    render(
      <WorkflowDataTable
        workflows={[makeWorkflow({ critical_issues_count: 5 })]}
        {...defaultProps}
      />
    )
    // Should render the critical count (5 is unique enough to not collide)
    expect(screen.getByText('5')).toBeInTheDocument()
  })

  it('shows dash for zero critical issues', () => {
    render(
      <WorkflowDataTable
        workflows={[makeWorkflow({ critical_issues_count: 0 })]}
        {...defaultProps}
      />
    )

    // Should show an em dash character
    const cells = screen.getAllByRole('cell')
    const criticalCell = cells.find(cell => cell.textContent === '\u2014')
    expect(criticalCell).toBeDefined()
  })

  it('renders orchestration pattern', () => {
    render(<WorkflowDataTable workflows={[makeWorkflow()]} {...defaultProps} />)
    expect(screen.getByText('sequential')).toBeInTheDocument()
  })

  it('shows all columns when Show All is clicked', async () => {
    const user = userEvent.setup()
    render(<WorkflowDataTable workflows={[makeWorkflow()]} {...defaultProps} />)

    await user.click(screen.getByText('Columns'))
    await user.click(screen.getByText('Show All'))

    // Hidden-by-default columns should now be visible in the table
    const table = screen.getByRole('table')
    expect(within(table).getByText('Workflow ID')).toBeInTheDocument()
    expect(within(table).getByText('Source')).toBeInTheDocument()
  })
})
