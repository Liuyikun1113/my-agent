import apiClient from './api'
import { Agent, AgentStatus, HumanInterventionRequest, HumanInterventionResponse } from '@/types/agent'

class AgentService {
  // Agent management
  async getAgents(): Promise<Agent[]> {
    return apiClient.get('/v1/agents')
  }

  async getAgent(agentId: string): Promise<Agent> {
    return apiClient.get(`/v1/agents/${agentId}`)
  }

  async updateAgent(agentId: string, updates: Partial<Agent>): Promise<Agent> {
    return apiClient.put(`/v1/agents/${agentId}`, updates)
  }

  async enableAgent(agentId: string): Promise<Agent> {
    return this.updateAgent(agentId, { is_enabled: true })
  }

  async disableAgent(agentId: string): Promise<Agent> {
    return this.updateAgent(agentId, { is_enabled: false })
  }

  // Agent status
  async getAgentStatus(agentId: string): Promise<AgentStatus> {
    return apiClient.get(`/v1/agents/${agentId}/status`)
  }

  async getAllAgentsStatus(): Promise<Record<string, AgentStatus>> {
    return apiClient.get('/v1/agents/status')
  }

  // Agent execution
  async executeAgent(agentId: string, sessionId: string, input: any): Promise<any> {
    return apiClient.post(`/v1/agents/${agentId}/execute`, {
      session_id: sessionId,
      input,
    })
  }

  async stopAgentExecution(agentId: string, taskId: string): Promise<void> {
    return apiClient.post(`/v1/agents/${agentId}/stop`, { task_id: taskId })
  }

  // Human intervention
  async requestHumanIntervention(request: HumanInterventionRequest): Promise<HumanInterventionResponse> {
    return apiClient.post('/v1/agents/intervention', request)
  }

  async getIntervention(interventionId: string): Promise<HumanInterventionResponse> {
    return apiClient.get(`/v1/agents/intervention/${interventionId}`)
  }

  async respondToIntervention(interventionId: string, response: string): Promise<HumanInterventionResponse> {
    return apiClient.post(`/v1/agents/intervention/${interventionId}/respond`, { response })
  }

  async cancelIntervention(interventionId: string): Promise<void> {
    return apiClient.delete(`/v1/agents/intervention/${interventionId}`)
  }

  // Agent orchestration
  async orchestrate(sessionId: string, input: string): Promise<any> {
    return apiClient.post('/v1/orchestrate', {
      session_id: sessionId,
      input,
    })
  }

  // Agent capabilities discovery
  async getAgentCapabilities(agentId: string): Promise<string[]> {
    return apiClient.get(`/v1/agents/${agentId}/capabilities`)
  }

  async findAgentsByCapability(capability: string): Promise<Agent[]> {
    return apiClient.get(`/v1/agents/capability/${capability}`)
  }

  // Agent metrics
  async getAgentMetrics(agentId: string, timeframe: 'hour' | 'day' | 'week' | 'month' = 'day'): Promise<any> {
    return apiClient.get(`/v1/agents/${agentId}/metrics?timeframe=${timeframe}`)
  }

  async getSystemMetrics(): Promise<any> {
    return apiClient.get('/v1/agents/metrics/system')
  }
}

// Create singleton instance
const agentService = new AgentService()

export default agentService