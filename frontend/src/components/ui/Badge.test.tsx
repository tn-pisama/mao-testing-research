import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { Badge, ConfidenceTierBadge } from './Badge'

describe('Badge', () => {
  it('renders children', () => {
    render(<Badge>Status</Badge>)
    expect(screen.getByText('Status')).toBeInTheDocument()
  })

  it('applies default variant classes', () => {
    render(<Badge>Default</Badge>)
    const badge = screen.getByText('Default')
    expect(badge.className).toContain('border-zinc-600')
    expect(badge.className).toContain('text-zinc-300')
  })

  it('applies success variant classes', () => {
    render(<Badge variant="success">Success</Badge>)
    const badge = screen.getByText('Success')
    expect(badge.className).toContain('text-green-400')
  })

  it('applies error variant classes', () => {
    render(<Badge variant="error">Error</Badge>)
    const badge = screen.getByText('Error')
    expect(badge.className).toContain('text-red-400')
  })

  it('applies warning variant classes', () => {
    render(<Badge variant="warning">Warning</Badge>)
    const badge = screen.getByText('Warning')
    expect(badge.className).toContain('text-amber-400')
  })

  it('applies info variant classes', () => {
    render(<Badge variant="info">Info</Badge>)
    const badge = screen.getByText('Info')
    expect(badge.className).toContain('text-blue-400')
  })

  it('applies sm size classes', () => {
    render(<Badge size="sm">Small</Badge>)
    const badge = screen.getByText('Small')
    expect(badge.className).toContain('px-2')
  })

  it('merges custom className', () => {
    render(<Badge className="my-custom">Custom</Badge>)
    expect(screen.getByText('Custom').className).toContain('my-custom')
  })

  it('forwards ref', () => {
    const ref = { current: null as HTMLSpanElement | null }
    render(<Badge ref={ref}>Ref</Badge>)
    expect(ref.current).toBeInstanceOf(HTMLSpanElement)
  })
})

describe('ConfidenceTierBadge', () => {
  it('renders nothing when tier is null', () => {
    const { container } = render(<ConfidenceTierBadge tier={null} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders nothing when tier is undefined', () => {
    const { container } = render(<ConfidenceTierBadge />)
    expect(container.innerHTML).toBe('')
  })

  it('renders HIGH tier with success variant', () => {
    render(<ConfidenceTierBadge tier="HIGH" />)
    const badge = screen.getByText('HIGH')
    expect(badge).toBeInTheDocument()
    expect(badge.className).toContain('text-green-400')
  })

  it('renders LIKELY tier with info variant', () => {
    render(<ConfidenceTierBadge tier="LIKELY" />)
    expect(screen.getByText('LIKELY')).toBeInTheDocument()
  })

  it('renders POSSIBLE tier with warning variant', () => {
    render(<ConfidenceTierBadge tier="POSSIBLE" />)
    expect(screen.getByText('POSSIBLE')).toBeInTheDocument()
  })

  it('renders LOW tier with error variant', () => {
    render(<ConfidenceTierBadge tier="LOW" />)
    const badge = screen.getByText('LOW')
    expect(badge).toBeInTheDocument()
    expect(badge.className).toContain('text-red-400')
  })

  it('handles case-insensitive tiers', () => {
    render(<ConfidenceTierBadge tier="high" />)
    expect(screen.getByText('HIGH')).toBeInTheDocument()
  })

  it('renders unknown tier with default variant', () => {
    render(<ConfidenceTierBadge tier="UNKNOWN" />)
    expect(screen.getByText('UNKNOWN')).toBeInTheDocument()
  })
})
