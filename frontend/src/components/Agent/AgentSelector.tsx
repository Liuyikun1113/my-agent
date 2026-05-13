import React, { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Box,
  Typography,
  Card,
  CardContent,
  CardActions,
  Button,
  Chip,
  Switch,
  Grid,
  IconButton,
  Tooltip,
  TextField,
  InputAdornment,
} from '@mui/material'
import SearchIcon from '@mui/icons-material/Search'
import RefreshIcon from '@mui/icons-material/Refresh'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import StopIcon from '@mui/icons-material/Stop'
import useAgentStore from '@/stores/agentStore'
import useSessionStore from '@/stores/sessionStore'
import { Agent, AgentStatus as AgentStatusType } from '@/types/agent'
import AgentStatusChip from './AgentStatus'

const capabilityLabels: Record<string, string> = {
  can_chat: 'Chat',
  can_tool_call: 'Tool Call',
  can_plan_execute: 'Plan & Execute',
  can_react: 'ReAct',
  can_research: 'Research',
  can_code: 'Coding',
}

const AgentSelector: React.FC = () => {
  const navigate = useNavigate()

  const {
    agents,
    agentStatus,
    isLoading,
    error,
    fetchAgents,
    fetchAllAgentStatus,
    enableAgent,
    disableAgent,
  } = useAgentStore()

  const currentSessionId = useSessionStore((s) => s.currentSessionId)

  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    fetchAgents()
    fetchAllAgentStatus()

    const interval = setInterval(fetchAllAgentStatus, 15000)
    return () => clearInterval(interval)
  }, [fetchAgents, fetchAllAgentStatus])

  const handleToggleAgent = useCallback(
    async (agentId: string, isEnabled: boolean) => {
      if (isEnabled) {
        await disableAgent(agentId)
      } else {
        await enableAgent(agentId)
      }
    },
    [enableAgent, disableAgent]
  )

  const filteredAgents = React.useMemo(() => {
    if (!searchQuery) return agents
    const q = searchQuery.toLowerCase()
    return agents.filter(
      (a) =>
        a.name.toLowerCase().includes(q) ||
        a.description?.toLowerCase().includes(q) ||
        a.type.toLowerCase().includes(q)
    )
  }, [agents, searchQuery])

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Box>
          <Typography variant="h5" fontWeight="bold">
            Agents
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {agents.length} agent{agents.length !== 1 ? 's' : ''} available
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Tooltip title="Refresh status">
            <IconButton onClick={fetchAllAgentStatus} disabled={isLoading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Search */}
      <TextField
        size="small"
        placeholder="Search agents..."
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        InputProps={{
          startAdornment: (
            <InputAdornment position="start">
              <SearchIcon fontSize="small" />
            </InputAdornment>
          ),
        }}
        sx={{ mb: 2 }}
      />

      {/* Agent grid */}
      <Box sx={{ flex: 1, overflow: 'auto' }}>
        <Grid container spacing={2}>
          {filteredAgents.map((agent) => {
            const status = agentStatus[agent.id]
            const isOnline = status?.status === 'idle' || status?.status === 'busy'

            return (
              <Grid item xs={12} sm={6} md={4} key={agent.id}>
                <Card
                  variant="outlined"
                  sx={{
                    borderRadius: 2,
                    transition: 'box-shadow 0.15s',
                    '&:hover': { boxShadow: 3 },
                  }}
                >
                  <CardContent sx={{ pb: 1 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
                      <Typography variant="subtitle1" fontWeight="bold">
                        {agent.name}
                      </Typography>
                      <Switch
                        size="small"
                        checked={agent.is_enabled}
                        onChange={() => handleToggleAgent(agent.id, agent.is_enabled)}
                      />
                    </Box>

                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                      {agent.description || 'No description'}
                    </Typography>

                    {/* Capabilities */}
                    <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mb: 1 }}>
                      {Object.entries(agent.capabilities)
                        .filter(([, v]) => v === true)
                        .map(([key]) => (
                          <Chip
                            key={key}
                            label={capabilityLabels[key] || key}
                            size="small"
                            variant="outlined"
                            sx={{ fontSize: '0.65rem', height: 20 }}
                          />
                        ))}
                    </Box>

                    {/* Status */}
                    <AgentStatusChip agent={agent} status={status} compact />
                  </CardContent>

                  <CardActions sx={{ pt: 0, justifyContent: 'flex-end' }}>
                    <Button
                      size="small"
                      onClick={() => navigate(`/sessions/${currentSessionId || 'new'}`)}
                    >
                      Chat
                    </Button>
                    <Tooltip title={isOnline ? 'Stop agent' : 'Start agent'}>
                      <IconButton
                        size="small"
                        color={isOnline ? 'error' : 'primary'}
                      >
                        {isOnline ? <StopIcon /> : <PlayArrowIcon />}
                      </IconButton>
                    </Tooltip>
                  </CardActions>
                </Card>
              </Grid>
            )
          })}
        </Grid>

        {filteredAgents.length === 0 && (
          <Box sx={{ textAlign: 'center', py: 8 }}>
            <Typography variant="h6" color="text.secondary">
              {searchQuery ? 'No matching agents' : 'No agents available'}
            </Typography>
          </Box>
        )}
      </Box>
    </Box>
  )
}

export default AgentSelector
