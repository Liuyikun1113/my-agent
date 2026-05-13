import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'
import { Session } from '@/types/session'
import apiClient from '@/services/api'

interface SessionStore {
  // State
  sessions: Session[]
  currentSessionId: string | null
  isLoading: boolean
  error: string | null

  // Actions
  setSessions: (sessions: Session[]) => void
  setCurrentSessionId: (sessionId: string | null) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void

  // API Actions
  fetchSessions: (page?: number, pageSize?: number) => Promise<void>
  createSession: (title?: string, description?: string, metadata?: Record<string, any>) => Promise<Session>
  updateSession: (sessionId: string, updates: Partial<Session>) => Promise<Session>
  deleteSession: (sessionId: string) => Promise<void>
  selectSession: (sessionId: string) => Promise<void>
  clearCurrentSession: () => void

  // Derived state
  getCurrentSession: () => Session | null
  getSessionById: (sessionId: string) => Session | null
}

const useSessionStore = create<SessionStore>()(
  devtools(
    persist(
      (set, get) => ({
        // Initial state
        sessions: [],
        currentSessionId: null,
        isLoading: false,
        error: null,

        // Basic setters
        setSessions: (sessions) => set({ sessions }),
        setCurrentSessionId: (sessionId) => set({ currentSessionId: sessionId }),
        setLoading: (loading) => set({ isLoading: loading }),
        setError: (error) => set({ error }),

        // API Actions
        fetchSessions: async (page = 1, pageSize = 20) => {
          set({ isLoading: true, error: null })
          try {
            const response = await apiClient.getSessions(page, pageSize)
            set({ sessions: response.items || response })
          } catch (error: any) {
            set({ error: error.message || 'Failed to fetch sessions' })
            console.error('Failed to fetch sessions:', error)
          } finally {
            set({ isLoading: false })
          }
        },

        createSession: async (title, description, metadata) => {
          set({ isLoading: true, error: null })
          try {
            const session = await apiClient.createSession(title, description, metadata)
            set((state) => ({
              sessions: [session, ...state.sessions],
              currentSessionId: session.id,
            }))
            return session
          } catch (error: any) {
            set({ error: error.message || 'Failed to create session' })
            console.error('Failed to create session:', error)
            throw error
          } finally {
            set({ isLoading: false })
          }
        },

        updateSession: async (sessionId, updates) => {
          set({ isLoading: true, error: null })
          try {
            const updatedSession = await apiClient.updateSession(sessionId, updates)
            set((state) => ({
              sessions: state.sessions.map((session) =>
                session.id === sessionId ? updatedSession : session
              ),
            }))
            return updatedSession
          } catch (error: any) {
            set({ error: error.message || 'Failed to update session' })
            console.error('Failed to update session:', error)
            throw error
          } finally {
            set({ isLoading: false })
          }
        },

        deleteSession: async (sessionId) => {
          set({ isLoading: true, error: null })
          try {
            await apiClient.deleteSession(sessionId)
            set((state) => ({
              sessions: state.sessions.filter((session) => session.id !== sessionId),
              currentSessionId:
                state.currentSessionId === sessionId ? null : state.currentSessionId,
            }))
          } catch (error: any) {
            set({ error: error.message || 'Failed to delete session' })
            console.error('Failed to delete session:', error)
            throw error
          } finally {
            set({ isLoading: false })
          }
        },

        selectSession: async (sessionId) => {
          set({ currentSessionId: sessionId })
          // Optionally fetch session details if not in store
          const session = get().getSessionById(sessionId)
          if (!session) {
            try {
              await apiClient.getSession(sessionId)
              // Session will be added to store via separate fetch
            } catch (error) {
              console.error('Failed to fetch session details:', error)
            }
          }
        },

        clearCurrentSession: () => {
          set({ currentSessionId: null })
        },

        // Derived state
        getCurrentSession: () => {
          const { currentSessionId, sessions } = get()
          return sessions.find((session) => session.id === currentSessionId) || null
        },

        getSessionById: (sessionId) => {
          const { sessions } = get()
          return sessions.find((session) => session.id === sessionId) || null
        },
      }),
      {
        name: 'session-storage',
        partialize: (state) => ({
          sessions: state.sessions,
          currentSessionId: state.currentSessionId,
        }),
      }
    ),
    {
      name: 'SessionStore',
    }
  )
)

export default useSessionStore