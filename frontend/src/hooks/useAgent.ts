import { useState, useCallback, useEffect } from 'react'
import useAgentStore from '@/stores/agentStore'
import useSessionStore from '@/stores/sessionStore'
import { Agent, AgentStatus, HumanInterventionRequest, HumanInterventionResponse } from '@/types/agent'

interface UseAgentOptions {
  agentId?: string
  autoFetch?: boolean
  onStatusChange?: (status: AgentStatus) => void
  onIntervention?: (intervention: HumanInterventionResponse) => void
}

export default function useAgent(options: UseAgentOptions = {}) {
  const {
    agentId: propAgentId,
    autoFetch = true,
    onStatusChange,
    onIntervention,
  } = options

  // Get current agent from store if not provided
  const currentAgent = useAgentStore((state) => state.getCurrentAgent())
  const agentId = propAgentId || currentAgent?.id

  // Get agent store actions and state
  const {
    agents,
    agentStatus,
    interventions,
    isLoading,
    error,
    fetchAgents: storeFetchAgents,
    fetchAgentStatus: storeFetchAgentStatus,
    fetchAllAgentStatus: storeFetchAllAgentStatus,
    updateAgent: storeUpdateAgent,
    enableAgent: storeEnableAgent,
    disableAgent: storeDisableAgent,
    executeAgent: storeExecuteAgent,
    stopAgentExecution: storeStopAgentExecution,
    requestHumanIntervention: storeRequestHumanIntervention,
    respondToIntervention: storeRespondToIntervention,
    cancelIntervention: storeCancelIntervention,
    fetchIntervention: storeFetchIntervention,
    orchestrate: storeOrchestrate,
    getAgentById: storeGetAgentById,
    getAgentStatusById: storeGetAgentStatusById,
    getActiveInterventions: storeGetActiveInterventions,
  } = useAgentStore()

  // Get current session
  const sessionId = useSessionStore((state) => state.currentSessionId)

  // Local state
  const [executionResult, setExecutionResult] = useState<any>(null)
  const [isExecuting, setIsExecuting] = useState(false)

  // Fetch agents on mount
  useEffect(() => {
    if (autoFetch) {
      storeFetchAgents().catch(console.error)
      storeFetchAllAgentStatus().catch(console.error)
    }
  }, [autoFetch])

  // Fetch agent status periodically
  useEffect(() => {
    if (!agentId) return

    const interval = setInterval(() => {
      storeFetchAgentStatus(agentId).catch(console.error)
    }, 10000) // Every 10 seconds

    return () => clearInterval(interval)
  }, [agentId])

  // Monitor status changes
  useEffect(() => {
    if (agentId && onStatusChange) {
      const status = storeGetAgentStatusById(agentId)
      if (status) {
        onStatusChange(status)
      }
    }
  }, [agentId, agentStatus, onStatusChange])

  // Monitor interventions
  useEffect(() => {
    if (onIntervention) {
      const activeInterventions = storeGetActiveInterventions()
      activeInterventions.forEach(onIntervention)
    }
  }, [interventions, onIntervention])

  // Get current agent and status
  const agent = agentId ? storeGetAgentById(agentId) : null
  const status = agentId ? storeGetAgentStatusById(agentId) : null

  // Agent execution
  const execute = useCallback(
    async (input: any, executeSessionId?: string) => {
      if (!agentId) {
        throw new Error('No agent selected')
      }

      const targetSessionId = executeSessionId || sessionId
      if (!targetSessionId) {
        throw new Error('No session selected')
      }

      setIsExecuting(true)
      setExecutionResult(null)

      try {
        const result = await storeExecuteAgent(agentId, targetSessionId, input)
        setExecutionResult(result)
        return result
      } catch (error) {
        console.error('Agent execution failed:', error)
        throw error
      } finally {
        setIsExecuting(false)
      }
    },
    [agentId, sessionId, storeExecuteAgent]
  )

  // Stop execution
  const stopExecution = useCallback(
    async (taskId: string) => {
      if (!agentId) {
        throw new Error('No agent selected')
      }

      try {
        await storeStopAgentExecution(agentId, taskId)
      } catch (error) {
        console.error('Failed to stop execution:', error)
        throw error
      }
    },
    [agentId, storeStopAgentExecution]
  )

  // Human intervention
  const requestIntervention = useCallback(
    async (request: Omit<HumanInterventionRequest, 'session_id'>) => {
      if (!sessionId) {
        throw new Error('No session selected')
      }

      const fullRequest: HumanInterventionRequest = {
        ...request,
        session_id: sessionId,
      }

      try {
        return await storeRequestHumanIntervention(fullRequest)
      } catch (error) {
        console.error('Failed to request intervention:', error)
        throw error
      }
    },
    [sessionId, storeRequestHumanIntervention]
  )

  // Respond to intervention
  const respondToIntervention = useCallback(
    async (interventionId: string, response: string) => {
      try {
        return await storeRespondToIntervention(interventionId, response)
      } catch (error) {
        console.error('Failed to respond to intervention:', error)
        throw error
      }
    },
    [storeRespondToIntervention]
  )

  // Orchestration
  const orchestrate = useCallback(
    async (input: string, orchestrateSessionId?: string) => {
      const targetSessionId = orchestrateSessionId || sessionId
      if (!targetSessionId) {
        throw new Error('No session selected')
      }

      try {
        return await storeOrchestrate(targetSessionId, input)
      } catch (error) {
        console.error('Orchestration failed:', error)
        throw error
      }
    },
    [sessionId, storeOrchestrate]
  )

  return {
    // State
    agent,
    status,
    agents,
    agentStatus,
    interventions: storeGetActiveInterventions(),
    isLoading,
    error,
    executionResult,
    isExecuting,

    // Actions
    execute,
    stopExecution,
    requestIntervention,
    respondToIntervention,
    cancelIntervention: storeCancelIntervention,
    fetchIntervention: storeFetchIntervention,
    orchestrate,

    // Agent management
    updateAgent: storeUpdateAgent,
    enableAgent: storeEnableAgent,
    disableAgent: storeDisableAgent,
    fetchAgentStatus: (id?: string) =>
      storeFetchAgentStatus(id || agentId || ''),
    fetchAllAgentStatus: storeFetchAllAgentStatus,

    // Selection
    selectAgent: useAgentStore((state) => state.setCurrentAgentId),

    // Utility
    getAgent: storeGetAgentById,
    getAgentStatus: storeGetAgentStatusById,
    hasAgent: !!agentId,
    canExecute: !!agentId && !!sessionId && !isExecuting,
  }
}