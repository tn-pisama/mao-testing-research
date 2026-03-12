import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { StatsCard } from './StatsCard'
import { Activity } from 'lucide-react'

describe('StatsCard', () => {
  it('renders title and value', () => {
    render(<StatsCard title="Total Traces" value={42} icon={Activity} />)
    expect(screen.getByText('Total Traces')).toBeInTheDocument()
    expect(screen.getByText('42')).toBeInTheDocument()
  })

  it('renders string value', () => {
    render(<StatsCard title="Status" value="Active" icon={Activity} />)
    expect(screen.getByText('Active')).toBeInTheDocument()
  })

  it('shows positive change with + prefix', () => {
    render(<StatsCard title="Traces" value={100} icon={Activity} change={15} />)
    expect(screen.getByText('+15%')).toBeInTheDocument()
  })

  it('shows negative change without + prefix', () => {
    render(<StatsCard title="Errors" value={5} icon={Activity} change={-10} />)
    expect(screen.getByText('-10%')).toBeInTheDocument()
  })

  it('shows default change label', () => {
    render(<StatsCard title="Traces" value={100} icon={Activity} change={5} />)
    expect(screen.getByText('vs last period')).toBeInTheDocument()
  })

  it('shows custom change label', () => {
    render(<StatsCard title="Traces" value={100} icon={Activity} change={5} changeLabel="vs yesterday" />)
    expect(screen.getByText('vs yesterday')).toBeInTheDocument()
  })

  it('does not show change section when change is undefined', () => {
    render(<StatsCard title="Traces" value={100} icon={Activity} />)
    expect(screen.queryByText('vs last period')).not.toBeInTheDocument()
    expect(screen.queryByText('%')).not.toBeInTheDocument()
  })

  it('applies green color for positive change', () => {
    render(<StatsCard title="Traces" value={100} icon={Activity} change={10} />)
    const changeText = screen.getByText('+10%')
    expect(changeText.className).toContain('text-green-500')
  })

  it('applies red color for negative change', () => {
    render(<StatsCard title="Traces" value={100} icon={Activity} change={-10} />)
    const changeText = screen.getByText('-10%')
    expect(changeText.className).toContain('text-red-500')
  })

  it('shows zero change as positive', () => {
    render(<StatsCard title="Traces" value={100} icon={Activity} change={0} />)
    expect(screen.getByText('+0%')).toBeInTheDocument()
  })

  it('renders with blue color by default', () => {
    const { container } = render(<StatsCard title="Test" value={1} icon={Activity} />)
    const iconContainer = container.querySelector('.bg-blue-500\\/10')
    expect(iconContainer).toBeInTheDocument()
  })

  it('renders with green color', () => {
    const { container } = render(<StatsCard title="Test" value={1} icon={Activity} color="green" />)
    const iconContainer = container.querySelector('.bg-green-500\\/20')
    expect(iconContainer).toBeInTheDocument()
  })

  it('renders with red color', () => {
    const { container } = render(<StatsCard title="Test" value={1} icon={Activity} color="red" />)
    const iconContainer = container.querySelector('.bg-red-500\\/20')
    expect(iconContainer).toBeInTheDocument()
  })
})
