export interface Session {
  id: string
  title: string | null
  description: string | null
  status: 'active' | 'paused' | 'completed' | 'archived'
  created_at: string
  updated_at: string
  metadata: Record<string, any> | null
  message_count: number
  last_message_at: string | null
}

export interface CreateSessionRequest {
  title?: string
  description?: string
  metadata?: Record<string, any>
}

export interface UpdateSessionRequest {
  title?: string
  description?: string
  status?: Session['status']
  metadata?: Record<string, any>
}

export interface SessionStats {
  total_sessions: number
  active_sessions: number
  total_messages: number
  average_messages_per_session: number
}