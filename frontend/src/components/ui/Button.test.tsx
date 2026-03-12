import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { Button } from './Button'

describe('Button', () => {
  it('renders children text', () => {
    render(<Button>Click me</Button>)
    expect(screen.getByRole('button', { name: /click me/i })).toBeInTheDocument()
  })

  it('applies primary variant classes by default', () => {
    render(<Button>Primary</Button>)
    const btn = screen.getByRole('button')
    expect(btn.className).toContain('bg-blue-600')
  })

  it('applies danger variant classes', () => {
    render(<Button variant="danger">Delete</Button>)
    const btn = screen.getByRole('button')
    expect(btn.className).toContain('bg-red-600')
  })

  it('applies success variant classes', () => {
    render(<Button variant="success">Save</Button>)
    const btn = screen.getByRole('button')
    expect(btn.className).toContain('bg-green-600')
  })

  it('applies secondary variant classes', () => {
    render(<Button variant="secondary">Cancel</Button>)
    const btn = screen.getByRole('button')
    expect(btn.className).toContain('border-zinc-700')
  })

  it('applies ghost variant classes', () => {
    render(<Button variant="ghost">Ghost</Button>)
    const btn = screen.getByRole('button')
    expect(btn.className).toContain('text-zinc-400')
  })

  it('applies size sm classes', () => {
    render(<Button size="sm">Small</Button>)
    const btn = screen.getByRole('button')
    expect(btn.className).toContain('px-3')
    expect(btn.className).toContain('text-xs')
  })

  it('applies size lg classes', () => {
    render(<Button size="lg">Large</Button>)
    const btn = screen.getByRole('button')
    expect(btn.className).toContain('px-6')
    expect(btn.className).toContain('text-base')
  })

  it('calls onClick handler when clicked', async () => {
    const user = userEvent.setup()
    const handleClick = vi.fn()
    render(<Button onClick={handleClick}>Click</Button>)

    await user.click(screen.getByRole('button'))
    expect(handleClick).toHaveBeenCalledTimes(1)
  })

  it('is disabled when disabled prop is true', async () => {
    const user = userEvent.setup()
    const handleClick = vi.fn()
    render(<Button disabled onClick={handleClick}>Disabled</Button>)

    const btn = screen.getByRole('button')
    expect(btn).toBeDisabled()

    await user.click(btn)
    expect(handleClick).not.toHaveBeenCalled()
  })

  it('is disabled when isLoading is true', () => {
    render(<Button isLoading>Loading</Button>)
    expect(screen.getByRole('button')).toBeDisabled()
  })

  it('is disabled when loading is true', () => {
    render(<Button loading>Loading</Button>)
    expect(screen.getByRole('button')).toBeDisabled()
  })

  it('shows spinner SVG when isLoading', () => {
    render(<Button isLoading>Loading</Button>)
    const btn = screen.getByRole('button')
    const svg = btn.querySelector('svg.animate-spin')
    expect(svg).toBeInTheDocument()
  })

  it('does not show spinner when not loading', () => {
    render(<Button>Not Loading</Button>)
    const btn = screen.getByRole('button')
    const svg = btn.querySelector('svg.animate-spin')
    expect(svg).not.toBeInTheDocument()
  })

  it('renders left icon when not loading', () => {
    render(<Button leftIcon={<span data-testid="left-icon">L</span>}>With Icon</Button>)
    expect(screen.getByTestId('left-icon')).toBeInTheDocument()
  })

  it('hides left icon when loading', () => {
    render(<Button isLoading leftIcon={<span data-testid="left-icon">L</span>}>With Icon</Button>)
    expect(screen.queryByTestId('left-icon')).not.toBeInTheDocument()
  })

  it('renders right icon', () => {
    render(<Button rightIcon={<span data-testid="right-icon">R</span>}>With Icon</Button>)
    expect(screen.getByTestId('right-icon')).toBeInTheDocument()
  })

  it('merges custom className', () => {
    render(<Button className="custom-class">Custom</Button>)
    const btn = screen.getByRole('button')
    expect(btn.className).toContain('custom-class')
  })

  it('forwards ref', () => {
    const ref = { current: null as HTMLButtonElement | null }
    render(<Button ref={ref}>Ref</Button>)
    expect(ref.current).toBeInstanceOf(HTMLButtonElement)
  })
})
