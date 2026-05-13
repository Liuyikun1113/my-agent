export type AgentType = 'orchestrator' | 'plan_execute' | 'react' | 'research' | 'coding' | 'interruption_handler' | 'specialized'

export interface Agent {
  id: string
  name: string
  type: AgentType
  description: string | null
  is_enabled: boolean
  capabilities: string[]
  configuration: Record<string, any>
  created_at: string
  updated_at: string
}

export interface AgentStatus {
  agent_id: string
  status: 'idle' | 'busy' | 'error' | 'offline'
  current_task: string | null
  task_progress: number | null
  last_heartbeat: string
  metrics: {
    tasks_completed: number
    tasks_failed: number
    average_response_time: number
  }
}

export interface AgentResponse {
  agent: Agent
  status: AgentStatus
}

export interface HumanInterventionRequest {
  session_id: string
  message_id: string
  intervention_type: 'approval' | 'clarification' | 'correction'
  request_message: string
  options?: string[]
}

export interface HumanInterventionResponse {
  intervention_id: string
  status: 'pending' | 'approved' | 'rejected' | 'cancelled'
  user_response: string | null
  responded_at: string | null
}