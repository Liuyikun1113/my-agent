import React, { memo } from 'react'
import {
  Box,
  Typography,
  Chip,
  LinearProgress,
  Tooltip,
  Paper,
} from '@mui/material'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import ErrorIcon from '@mui/icons-material/Error'
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty'
import OfflineBoltIcon from '@mui/icons-material/OfflineBolt'
import { Agent, AgentStatus as AgentStatusType } from '@/types/agent'

interface AgentStatusProps {
  agent: Agent
  status?: AgentStatusType | null
  compact?: boolean
}

const statusConfig = {
  idle: { color: 'success' as const, icon: CheckCircleIcon, label: 'Idle' },
  busy: { color: 'warning' as const, icon: HourglassEmptyIcon, label: 'Busy' },
  error: { color: 'error' as const, icon: ErrorIcon, label: 'Error' },
  offline: { color: 'default' as const, icon: OfflineBoltIcon, label: 'Offline' },
}

const AgentStatusChip: React.FC<AgentStatusProps> = memo(({ agent, status, compact = false }) => {
  const s = status || { status: 'offline' as const, last_heartbeat: '', metrics: { tasks_completed: 0, tasks_failed: 0, average_response_time: 0 } }
  const config = statusConfig[s.status] || statusConfig.offline
  const StatusIcon = config.icon

  const uptime = s.last_heartbeat
    ? Math.round((Date.now() - new Date(s.last_heartbeat).getTime()) / 1000)
    : null

  if (compact) {
    return (
      <Tooltip title={`${agent.name}: ${config.label}`}>
        <Chip
          icon={<StatusIcon />}
          label={agent.name}
          size="small"
          color={config.color}
          variant="outlined"
          sx={{ height: 24 }}
        />
      </Tooltip>
    )
  }

  return (
    <Paper
      variant="outlined"
      sx={{
        p: 1.5,
        borderRadius: 2,
        borderColor: s.status === 'busy' ? 'warning.main' : 'divider',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <StatusIcon fontSize="small" color={config.color} />
          <Typography variant="body2" fontWeight="medium">
            {agent.name}
          </Typography>
        </Box>
        <Chip
          label={config.label}
          size="small"
          color={config.color}
          variant="filled"
          sx={{ height: 20, fontSize: '0.7rem' }}
        />
      </Box>

      {/* Current task */}
      {s.current_task && (
        <Box sx={{ mt: 0.5 }}>
          <Typography variant="caption" color="text.secondary" noWrap>
            Task: {s.current_task}
          </Typography>
          {s.task_progress != null && (
            <LinearProgress
              variant="determinate"
              value={s.task_progress}
              sx={{ mt: 0.5, borderRadius: 1, height: 4 }}
            />
          )}
        </Box>
      )}

      {/* Metrics */}
      <Box sx={{ display: 'flex', gap: 2, mt: 1 }}>
        <Typography variant="caption" color="text.secondary">
          Completed: {s.metrics?.tasks_completed || 0}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Failed: {s.metrics?.tasks_failed || 0}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Avg: {(s.metrics?.average_response_time || 0).toFixed(1)}s
        </Typography>
      </Box>

      {/* Heartbeat */}
      {uptime != null && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.25 }}>
          Last seen: {uptime < 60 ? `${uptime}s ago` : `${Math.round(uptime / 60)}m ago`}
        </Typography>
      )}
    </Paper>
  )
})

AgentStatusChip.displayName = 'AgentStatusChip'

export default AgentStatusChip
