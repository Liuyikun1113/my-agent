import React, { memo } from 'react'
import {
  Paper,
  Box,
  Typography,
  IconButton,
  Chip,
  Tooltip,
} from '@mui/material'
import ChatIcon from '@mui/icons-material/Chat'
import DeleteIcon from '@mui/icons-material/Delete'
import EditIcon from '@mui/icons-material/Edit'
import MoreVertIcon from '@mui/icons-material/MoreVert'
import { Session } from '@/types/session'
import { formatDistanceToNow } from 'date-fns'

interface SessionCardProps {
  session: Session
  isActive?: boolean
  onClick?: (session: Session) => void
  onEdit?: (session: Session) => void
  onDelete?: (session: Session) => void
}

const statusColors: Record<string, 'success' | 'warning' | 'info' | 'default'> = {
  active: 'success',
  paused: 'warning',
  completed: 'info',
  archived: 'default',
}

const SessionCard: React.FC<SessionCardProps> = memo(({
  session,
  isActive,
  onClick,
  onEdit,
  onDelete,
}) => {
  const lastActivity = session.last_message_at
    ? formatDistanceToNow(new Date(session.last_message_at), { addSuffix: true })
    : formatDistanceToNow(new Date(session.created_at), { addSuffix: true })

  return (
    <Paper
      elevation={isActive ? 2 : 0}
      sx={{
        p: 1.5,
        cursor: 'pointer',
        border: 1,
        borderColor: isActive ? 'primary.main' : 'divider',
        borderRadius: 2,
        bgcolor: isActive ? 'primary.light' : 'background.paper',
        transition: 'all 0.15s ease',
        '&:hover': {
          borderColor: 'primary.main',
          bgcolor: 'action.hover',
          elevation: 1,
        },
      }}
      onClick={() => onClick?.(session)}
    >
      <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        {/* Left: icon + info */}
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.5, flex: 1, minWidth: 0 }}>
          <Box
            sx={{
              width: 36,
              height: 36,
              borderRadius: 1.5,
              bgcolor: isActive ? 'primary.main' : 'grey.200',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: isActive ? 'white' : 'text.secondary',
              flexShrink: 0,
            }}
          >
            <ChatIcon fontSize="small" />
          </Box>

          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography
              variant="body2"
              fontWeight={isActive ? 'bold' : 'medium'}
              noWrap
              title={session.title || `Session ${session.id.slice(0, 8)}`}
            >
              {session.title || `Session ${session.id.slice(0, 8)}`}
            </Typography>

            {session.description && (
              <Typography
                variant="caption"
                color="text.secondary"
                noWrap
                sx={{ display: 'block' }}
              >
                {session.description}
              </Typography>
            )}

            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
              <Typography variant="caption" color="text.secondary">
                {lastActivity}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                &middot;
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {session.message_count} msg{session.message_count !== 1 ? 's' : ''}
              </Typography>
              <Chip
                label={session.status}
                size="small"
                color={statusColors[session.status] || 'default'}
                variant="outlined"
                sx={{ height: 18, fontSize: '0.6rem' }}
              />
            </Box>
          </Box>
        </Box>

        {/* Right: actions */}
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', ml: 1 }}>
          <Tooltip title="Edit">
            <IconButton
              size="small"
              onClick={(e) => {
                e.stopPropagation()
                onEdit?.(session)
              }}
              sx={{ opacity: 0.4, '&:hover': { opacity: 1 } }}
            >
              <EditIcon sx={{ fontSize: 16 }} />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete">
            <IconButton
              size="small"
              onClick={(e) => {
                e.stopPropagation()
                onDelete?.(session)
              }}
              sx={{ opacity: 0.4, '&:hover': { opacity: 1, color: 'error.main' } }}
            >
              <DeleteIcon sx={{ fontSize: 16 }} />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>
    </Paper>
  )
})

SessionCard.displayName = 'SessionCard'

export default SessionCard
