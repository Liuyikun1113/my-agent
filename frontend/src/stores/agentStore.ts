import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import { Agent, AgentStatus, HumanInterventionRequest, HumanInterventionResponse } from '@/types/agent'
import agentService from '@/services/agentService'

interface AgentStore {
  // State
  agents: Agent[]
  agentStatus: Record<string, AgentStatus> // agentId -> status
  currentAgentId: string | null
  interventions: Record<string, HumanInterventionResponse> // interventionId -> response
  isLoading: boolean
  error: string | null

  // Actions
  setAgents: (agents: Agent[]) => void
  setAgentStatus: (agentId: string, status: AgentStatus) => void
  setAllAgentStatus: (statuses: Record<string, AgentStatus>) => void
  setCurrentAgentId: (agentId: string | null) => void
  setIntervention: (interventionId: string, response: HumanInterventionResponse) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void

  // API Actions
  fetchAgents: () => Promise<void>
  fetchAgentStatus: (agentId: string) => Promise<void>
  fetchAllAgentStatus: () => Promise<void>
  updateAgent: (agentId: string, updates: Partial<Agent>) => Promise<Agent>
  enableAgent: (agentId: string) => Promise<Agent>
  disableAgent: (agentId: string) => Promise<Agent>

  // Execution Actions
  executeAgent: (agentId: string, sessionId: string, input: any) => Promise<any>
  stopAgentExecution: (agentId: string, taskId: string) => Promise<void>

  // Human Intervention Actions
  requestHumanIntervention: (request: HumanInterventionRequest) => Promise<HumanInterventionResponse>
  respondToIntervention: (interventionId: string, response: string) => Promise<HumanInterventionResponse>
  cancelIntervention: (interventionId: string) => Promise<void>
  fetchIntervention: (interventionId: string) => Promise<HumanInterventionResponse>

  // Orchestration Actions
  orchestrate: (sessionId: string, input: string) => Promise<any>

  // Derived state
  getCurrentAgent: () => Agent | null
  getAgentById: (agentId: string) => Agent | null
  getAgentStatusById: (agentId: string) => AgentStatus | null
  getActiveInterventions: () => HumanInterventionResponse[]
}

const useAgentStore = create<AgentStore>()(
  devtools(
    (set, get) => ({
      // Initial state
      agents: [],
      agentStatus: {},
      currentAgentId: null,
      interventions: {},
      isLoading: false,
      error: null,

      // Basic setters
      setAgents: (agents) => set({ agents }),
      setAgentStatus: (agentId, status) =>
        set((state) => ({
          agentStatus: {
            ...state.agentStatus,
            [agentId]: status,
          },
        })),
      setAllAgentStatus: (statuses) => set({ agentStatus: statuses }),
      setCurrentAgentId: (agentId) => set({ currentAgentId: agentId }),
      setIntervention: (interventionId, response) =>
        set((state) => ({
          interventions: {
            ...state.interventions,
            [interventionId]: response,
          },
        })),
      setLoading: (loading) => set({ isLoading: loading }),
      setError: (error) => set({ error }),

      // API Actions
      fetchAgents: async () => {
        set({ isLoading: true, error: null })
        try {
          const agents = await agentService.getAgents()
          set({ agents })
        } catch (error: any) {
          set({ error: error.message || 'Failed to fetch agents' })
          console.error('Failed to fetch agents:', error)
        } finally {
          set({ isLoading: false })
        }
      },

      fetchAgentStatus: async (agentId) => {
        try {
          const status = await agentService.getAgentStatus(agentId)
          get().setAgentStatus(agentId, status)
        } catch (error: any) {
          console.error(`Failed to fetch status for agent ${agentId}:`, error)
        }
      },

      fetchAllAgentStatus: async () => {
        try {
          const statuses = await agentService.getAllAgentsStatus()
          set({ agentStatus: statuses })
        } catch (error: any) {
          console.error('Failed to fetch all agent status:', error)
        }
      },

      updateAgent: async (agentId, updates) => {
        set({ isLoading: true, error: null })
        try {
          const updatedAgent = await agentService.updateAgent(agentId, updates)
          set((state) => ({
            agents: state.agents.map((agent) =>
              agent.id === agentId ? updatedAgent : agent
            ),
          }))
          return updatedAgent
        } catch (error: any) {
          set({ error: error.message || 'Failed to update agent' })
          console.error('Failed to update agent:', error)
          throw error
        } finally {
          set({ isLoading: false })
        }
      },

      enableAgent: async (agentId) => {
        return get().updateAgent(agentId, { is_enabled: true })
      },

      disableAgent: async (agentId) => {
        return get().updateAgent(agentId, { is_enabled: false })
      },

      // Execution Actions
      executeAgent: async (agentId, sessionId, input) => {
        set({ isLoading: true, error: null })
        try {
          const result = await agentService.executeAgent(agentId, sessionId, input)
          // Update agent status to busy
          get().setAgentStatus(agentId, {
            ...get().getAgentStatusById(agentId)!,
            status: 'busy',
            current_task: `Executing: ${JSON.stringify(input).slice(0, 50)}...`,
            task_progress: 0,
          })
          return result
        } catch (error: any) {
          set({ error: error.message || 'Failed to execute agent' })
          console.error('Failed to execute agent:', error)
          throw error
        } finally {
          set({ isLoading: false })
        }
      },

      stopAgentExecution: async (agentId, taskId) => {
        try {
          await agentService.stopAgentExecution(agentId, taskId)
          // Update agent status to idle
          get().setAgentStatus(agentId, {
            ...get().getAgentStatusById(agentId)!,
            status: 'idle',
            current_task: null,
            task_progress: null,
          })
        } catch (error: any) {
          console.error('Failed to stop agent execution:', error)
          throw error
        }
      },

      // Human Intervention Actions
      requestHumanIntervention: async (request) => {
        set({ isLoading: true, error: null })
        try {
          const response = await agentService.requestHumanIntervention(request)
          get().setIntervention(response.intervention_id, response)
          return response
        } catch (error: any) {
          set({ error: error.message || 'Failed to request human intervention' })
          console.error('Failed to request human intervention:', error)
          throw error
        } finally {
          set({ isLoading: false })
        }
      },

      respondToIntervention: async (interventionId, response) => {
        set({ isLoading: true, error: null })
        try {
          const updatedResponse = await agentService.respondToIntervention(interventionId, response)
          get().setIntervention(interventionId, updatedResponse)
          return updatedResponse
        } catch (error: any) {
          set({ error: error.message || 'Failed to respond to intervention' })
          console.error('Failed to respond to intervention:', error)
          throw error
        } finally {
          set({ isLoading: false })
        }
      },

      cancelIntervention: async (interventionId) => {
        try {
          await agentService.cancelIntervention(interventionId)
          // Remove intervention from store
          set((state) => {
            const interventions = { ...state.interventions }
            delete interventions[interventionId]
            return { interventions }
          })
        } catch (error: any) {
          console.error('Failed to cancel intervention:', error)
          throw error
        }
      },

      fetchIntervention: async (interventionId) => {
        try {
          const response = await agentService.getIntervention(interventionId)
          get().setIntervention(interventionId, response)
          return response
        } catch (error: any) {
          console.error('Failed to fetch intervention:', error)
          throw error
        }
      },

      // Orchestration Actions
      orchestrate: async (sessionId, input) => {
        set({ isLoading: true, error: null })
        try {
          const result = await agentService.orchestrate(sessionId, input)
          return result
        } catch (error: any) {
          set({ error: error.message || 'Failed to orchestrate' })
          console.error('Failed to orchestrate:', error)
          throw error
        } finally {
          set({ isLoading: false })
        }
      },

      // Derived state
      getCurrentAgent: () => {
        const { currentAgentId, agents } = get()
        return agents.find((agent) => agent.id === currentAgentId) || null
      },

      getAgentById: (agentId) => {
        const { agents } = get()
        return agents.find((agent) => agent.id === agentId) || null
      },

      getAgentStatusById: (agentId) => {
        return get().agentStatus[agentId] || null
      },

      getActiveInterventions: () => {
        const { interventions } = get()
        return Object.values(interventions).filter(
          (intervention) => intervention.status === 'pending'
        )
      },
    }),
    {
      name: 'AgentStore',
    }
  )
)

export default useAgentStore