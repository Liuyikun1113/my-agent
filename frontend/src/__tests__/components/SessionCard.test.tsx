import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import SessionCard from '@components/Session/SessionCard'
import { Session } from '@/types/session'
import { ThemeProvider, createTheme } from '@mui/material'

const theme = createTheme()

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <ThemeProvider theme={theme}>{children}</ThemeProvider>
)

const baseSession: Session = {
  id: 's1',
  title: 'Test Session',
  description: 'A test session',
  status: 'active',
  created_at: '2026-04-30T10:00:00Z',
  updated_at: '2026-04-30T10:30:00Z',
  metadata: null,
  message_count: 5,
  last_message_at: '2026-04-30T10:30:00Z',
}

describe('SessionCard', () => {
  it('should render session title', () => {
    render(<SessionCard session={baseSession} />, { wrapper })
    expect(screen.getByText('Test Session')).toBeInTheDocument()
  })

  it('should render message count', () => {
    render(<SessionCard session={baseSession} />, { wrapper })
    expect(screen.getByText('5')).toBeInTheDocument()
  })

  it('should call onClick when clicked', () => {
    const onClick = vi.fn()
    render(<SessionCard session={baseSession} onClick={onClick} />, { wrapper })

    fireEvent.click(screen.getByText('Test Session'))
    expect(onClick).toHaveBeenCalledWith('s1')
  })

  it('should show active status chip', () => {
    render(<SessionCard session={baseSession} />, { wrapper })
    const chip = screen.getByText('active')
    expect(chip).toBeInTheDocument()
  })

  it('should show completed status chip', () => {
    const completed: Session = { ...baseSession, status: 'completed' }
    render(<SessionCard session={completed} />, { wrapper })
    const chip = screen.getByText('completed')
    expect(chip).toBeInTheDocument()
  })

  it('should show paused status chip', () => {
    const paused: Session = { ...baseSession, status: 'paused' }
    render(<SessionCard session={paused} />, { wrapper })
    const chip = screen.getByText('paused')
    expect(chip).toBeInTheDocument()
  })

  it('should call onDelete when delete button clicked', () => {
    const onDelete = vi.fn()
    render(<SessionCard session={baseSession} onDelete={onDelete} />, { wrapper })

    const deleteBtn = screen.getByRole('button', { name: /delete/i })
    fireEvent.click(deleteBtn)
    expect(onDelete).toHaveBeenCalledWith('s1')
  })

  it('should show relative timestamp', () => {
    render(<SessionCard session={baseSession} />, { wrapper })
    // Should show something about the time
    expect(screen.getByText(/ago|min|hour|now/)).toBeInTheDocument()
  })

  it('should handle session without title', () => {
    const untitled: Session = { ...baseSession, title: null }
    render(<SessionCard session={untitled} />, { wrapper })
    // Should show a default label
    expect(screen.getByText(/Untitled|New|Session/)).toBeInTheDocument()
  })
})
