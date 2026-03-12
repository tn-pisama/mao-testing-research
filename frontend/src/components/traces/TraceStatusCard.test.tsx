import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { TraceStatusCard } from './TraceStatusCard'
import type { Trace } from '@/lib/api'

// Mock next/link to render as a plain anchor
vi.mock('next/link', () => ({
  default: ({ href, children, ...props }: any) => (
    <a href={href} {...props}>{children}</a>
  ),
}))

function makeTrace(overrides: Partial<Trace> = {}): Trace {
  return {
    id: 'trace-001',
    session_id: 'session-001',
    framework: 'n8n',
    status: 'completed',
    total_tokens: 1000,
    total_cost_cents: 5,
    created_at: new Date().toISOString(),
    state_count: 10,
    detection_count: 2,
    ...overrides,
  }
}

describe('TraceStatusCard', () => {
  it('renders the title', () => {
    render(<TraceStatusCard traces={[makeTrace()]} />)
    expect(screen.getByText('Trace Status')).toBeInTheDocument()
  })

  it('renders loading skeleton when isLoading', () => {
    const { container } = render(<TraceStatusCard traces={[]} isLoading />)
    const skeleton = container.querySelector('.animate-pulse')
    expect(skeleton).toBeInTheDocument()
  })

  it('does not render loading skeleton when not loading', () => {
    const { container } = render(<TraceStatusCard traces={[]} />)
    const skeleton = container.querySelector('.animate-pulse')
    expect(skeleton).not.toBeInTheDocument()
  })

  it('shows "No recent traces" when empty', () => {
    render(<TraceStatusCard traces={[]} />)
    expect(screen.getByText('No recent traces')).toBeInTheDocument()
  })

  it('shows status counts', () => {
    const traces = [
      makeTrace({ id: 't1', status: 'completed' }),
      makeTrace({ id: 't2', status: 'completed' }),
      makeTrace({ id: 't3', status: 'running' }),
      makeTrace({ id: 't4', status: 'failed' }),
    ]
    render(<TraceStatusCard traces={traces} />)

    // Find the parent container that has both the count and label text
    const completedLabel = screen.getByText('Completed')
    const completedSection = completedLabel.closest('.text-center')!
    expect(completedSection.textContent).toContain('2')

    const runningLabel = screen.getByText('Running')
    const runningSection = runningLabel.closest('.text-center')!
    expect(runningSection.textContent).toContain('1')

    const failedLabel = screen.getByText('Failed')
    const failedSection = failedLabel.closest('.text-center')!
    expect(failedSection.textContent).toContain('1')
  })

  it('shows zero counts when no traces match status', () => {
    render(<TraceStatusCard traces={[]} />)

    const completedLabel = screen.getByText('Completed')
    const completedSection = completedLabel.closest('.text-center')!
    expect(completedSection.textContent).toContain('0')

    const runningLabel = screen.getByText('Running')
    const runningSection = runningLabel.closest('.text-center')!
    expect(runningSection.textContent).toContain('0')

    const failedLabel = screen.getByText('Failed')
    const failedSection = failedLabel.closest('.text-center')!
    expect(failedSection.textContent).toContain('0')
  })

  it('renders trace IDs (truncated) in the list', () => {
    render(<TraceStatusCard traces={[makeTrace({ id: 'trace-abcdef1234567890' })]} />)
    expect(screen.getByText('trace-ab...')).toBeInTheDocument()
  })

  it('renders framework badge', () => {
    render(<TraceStatusCard traces={[makeTrace({ framework: 'n8n' })]} />)
    expect(screen.getByText('n8n')).toBeInTheDocument()
  })

  it('limits displayed traces to 4', () => {
    const traces = Array.from({ length: 6 }, (_, i) =>
      makeTrace({ id: `trace-${String(i).padStart(16, '0')}` })
    )
    render(<TraceStatusCard traces={traces} />)

    // Should show only 4 trace links
    const links = screen.getAllByRole('link').filter(link =>
      link.getAttribute('href')?.startsWith('/traces/')
    )
    expect(links).toHaveLength(4)
  })

  it('links to View all traces page', () => {
    render(<TraceStatusCard traces={[makeTrace()]} />)
    const viewAllLink = screen.getByText('View all')
    expect(viewAllLink.closest('a')).toHaveAttribute('href', '/traces')
  })

  it('links each trace to its detail page', () => {
    render(<TraceStatusCard traces={[makeTrace({ id: 'trace-abc' })]} />)
    const traceLink = screen.getByText('trace-ab...').closest('a')
    expect(traceLink).toHaveAttribute('href', '/traces/trace-abc')
  })
})
