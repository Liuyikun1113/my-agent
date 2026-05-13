import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act } from '@testing-library/react'

// Mock the API service BEFORE importing the store
vi.mock('@/services/api', () => ({
  default: {
    getSessions: vi.fn().mockResolvedValue({
      items: [
        { id: '1', title: 'Test 1', status: 'active', created_at: '2026-04-30T00:00:00Z', updated_at: '2026-04-30T00:00:00Z', message_count: 3 },
        { id: '2', title: 'Test 2', status: 'completed', created_at: '2026-04-29T00:00:00Z', updated_at: '2026-04-29T00:00:00Z', message_count: 10 },
      ],
    }),
    createSession: vi.fn().mockResolvedValue({
      id: 'new-1', title: 'New Session', status: 'active', created_at: '2026-04-30T12:00:00Z', updated_at: '2026-04-30T12:00:00Z', message_count: 0,
    }),
    updateSession: vi.fn().mockResolvedValue({
      id: '1', title: 'Updated Title', status: 'active', created_at: '2026-04-30T00:00:00Z', updated_at: '2026-04-30T12:00:00Z', message_count: 3,
    }),
    deleteSession: vi.fn().mockResolvedValue(undefined),
    getSession: vi.fn().mockResolvedValue({
      id: '1', title: 'Test 1', status: 'active', created_at: '2026-04-30T00:00:00Z', updated_at: '2026-04-30T00:00:00Z', message_count: 3,
    }),
  },
}))

import useSessionStore from '@stores/sessionStore'

describe('useSessionStore', () => {
  beforeEach(() => {
    const { resetState } = useSessionStore.getInitialState() as any
    useSessionStore.setState({
      sessions: [],
      currentSessionId: null,
      isLoading: false,
      error: null,
    })
  })

  it('should initialize with empty state', () => {
    const state = useSessionStore.getState()
    expect(state.sessions).toEqual([])
    expect(state.currentSessionId).toBeNull()
    expect(state.isLoading).toBe(false)
    expect(state.error).toBeNull()
  })

  it('should set sessions', () => {
    const sessions = [
      { id: '1', title: 'A', status: 'active' as const, created_at: '', updated_at: '', message_count: 0 },
    ]
    useSessionStore.getState().setSessions(sessions)
    expect(useSessionStore.getState().sessions).toHaveLength(1)
  })

  it('should set current session ID', () => {
    useSessionStore.getState().setCurrentSessionId('session-1')
    expect(useSessionStore.getState().currentSessionId).toBe('session-1')
  })

  it('should fetch sessions and populate store', async () => {
    await act(async () => {
      await useSessionStore.getState().fetchSessions(1, 20)
    })
    const state = useSessionStore.getState()
    expect(state.sessions).toHaveLength(2)
    expect(state.isLoading).toBe(false)
    expect(state.error).toBeNull()
  })

  it('should create session and set as current', async () => {
    await act(async () => {
      await useSessionStore.getState().createSession('New Session')
    })
    const state = useSessionStore.getState()
    expect(state.sessions).toHaveLength(1)
    expect(state.currentSessionId).toBe('new-1')
    expect(state.sessions[0].title).toBe('New Session')
  })

  it('should delete session and clear current if deleted', async () => {
    // Set up session to delete
    useSessionStore.getState().setSessions([
      { id: '1', title: 'A', status: 'active', created_at: '', updated_at: '', message_count: 0 },
    ])
    useSessionStore.getState().setCurrentSessionId('1')

    await act(async () => {
      await useSessionStore.getState().deleteSession('1')
    })

    const state = useSessionStore.getState()
    expect(state.sessions).toHaveLength(0)
    expect(state.currentSessionId).toBeNull()
  })

  it('should get current session', () => {
    const session = { id: '1', title: 'A', status: 'active' as const, created_at: '', updated_at: '', message_count: 0 }
    useSessionStore.getState().setSessions([session])
    useSessionStore.getState().setCurrentSessionId('1')

    const result = useSessionStore.getState().getCurrentSession()
    expect(result).toEqual(session)
  })

  it('should return null for non-existent session', () => {
    const result = useSessionStore.getState().getSessionById('does-not-exist')
    expect(result).toBeNull()
  })

  it('should clear current session', () => {
    useSessionStore.getState().setCurrentSessionId('session-1')
    useSessionStore.getState().clearCurrentSession()
    expect(useSessionStore.getState().currentSessionId).toBeNull()
  })
})
