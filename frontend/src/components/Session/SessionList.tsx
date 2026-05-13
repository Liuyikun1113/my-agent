import React, { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Box,
  Typography,
  TextField,
  InputAdornment,
  Button,
  IconButton,
  Tooltip,
  Divider,
  Chip,
  Stack,
} from '@mui/material'
import SearchIcon from '@mui/icons-material/Search'
import AddIcon from '@mui/icons-material/Add'
import SortIcon from '@mui/icons-material/Sort'
import FilterListIcon from '@mui/icons-material/FilterList'
import RefreshIcon from '@mui/icons-material/Refresh'
import useSessionStore from '@/stores/sessionStore'
import { Session } from '@/types/session'
import SessionCard from './SessionCard'
import NewSessionModal from './NewSessionModal'

const SessionList: React.FC = () => {
  const navigate = useNavigate()

  const {
    sessions,
    currentSessionId,
    isLoading,
    error,
    fetchSessions,
    createSession,
    deleteSession,
    updateSession,
    selectSession,
  } = useSessionStore()

  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string | null>(null)
  const [showNewModal, setShowNewModal] = useState(false)
  const [sortOrder, setSortOrder] = useState<'newest' | 'oldest'>('newest')

  // Filter and sort sessions
  const filteredSessions = React.useMemo(() => {
    let filtered = [...sessions]

    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      filtered = filtered.filter(
        (s) =>
          (s.title && s.title.toLowerCase().includes(query)) ||
          (s.description && s.description.toLowerCase().includes(query)) ||
          s.id.toLowerCase().includes(query)
      )
    }

    if (statusFilter) {
      filtered = filtered.filter((s) => s.status === statusFilter)
    }

    filtered.sort((a, b) => {
      const dateA = new Date(a.updated_at).getTime()
      const dateB = new Date(b.updated_at).getTime()
      return sortOrder === 'newest' ? dateB - dateA : dateA - dateB
    })

    return filtered
  }, [sessions, searchQuery, statusFilter, sortOrder])

  const handleSessionClick = useCallback(
    (session: Session) => {
      selectSession(session.id)
      navigate(`/sessions/${session.id}`)
    },
    [selectSession, navigate]
  )

  const handleCreateSession = useCallback(
    async (title?: string, description?: string) => {
      await createSession(title, description)
    },
    [createSession]
  )

  const handleDeleteSession = useCallback(
    async (session: Session) => {
      if (window.confirm(`Delete session "${session.title || session.id.slice(0, 8)}"?`)) {
        await deleteSession(session.id)
      }
    },
    [deleteSession]
  )

  const handleEditSession = useCallback(
    (session: Session) => {
      const newTitle = window.prompt('Edit title:', session.title || '')
      if (newTitle !== null) {
        updateSession(session.id, { title: newTitle })
      }
    },
    [updateSession]
  )

  const statusFilters = ['active', 'paused', 'completed', 'archived']

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Box>
          <Typography variant="h5" fontWeight="bold">
            Sessions
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {sessions.length} total session{sessions.length !== 1 ? 's' : ''}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Tooltip title="Refresh">
            <IconButton onClick={() => fetchSessions()} disabled={isLoading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setShowNewModal(true)}
          >
            New Session
          </Button>
        </Box>
      </Box>

      {/* Search and filters */}
      <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
        <TextField
          size="small"
          placeholder="Search sessions..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize="small" />
              </InputAdornment>
            ),
          }}
          sx={{ flex: 1 }}
        />
        <Tooltip title={`Sort: ${sortOrder}`}>
          <IconButton
            size="small"
            onClick={() => setSortOrder((o) => (o === 'newest' ? 'oldest' : 'newest'))}
          >
            <SortIcon />
          </IconButton>
        </Tooltip>
        <Tooltip title="Filter by status">
          <IconButton size="small">
            <FilterListIcon />
          </IconButton>
        </Tooltip>
      </Stack>

      {/* Status filter chips */}
      <Box sx={{ display: 'flex', gap: 0.5, mb: 2, flexWrap: 'wrap' }}>
        <Chip
          label="All"
          size="small"
          color={!statusFilter ? 'primary' : 'default'}
          variant={!statusFilter ? 'filled' : 'outlined'}
          onClick={() => setStatusFilter(null)}
        />
        {statusFilters.map((status) => (
          <Chip
            key={status}
            label={status}
            size="small"
            color={statusFilter === status ? 'primary' : 'default'}
            variant={statusFilter === status ? 'filled' : 'outlined'}
            onClick={() => setStatusFilter(statusFilter === status ? null : status)}
          />
        ))}
      </Box>

      {/* Session list */}
      <Box
        sx={{
          flex: 1,
          overflow: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 1,
        }}
      >
        {filteredSessions.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 8 }}>
            <Typography variant="h6" color="text.secondary">
              {searchQuery || statusFilter ? 'No matching sessions' : 'No sessions yet'}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {searchQuery || statusFilter
                ? 'Try adjusting your filters'
                : 'Create your first session to get started'}
            </Typography>
            {!searchQuery && !statusFilter && (
              <Button
                variant="outlined"
                startIcon={<AddIcon />}
                onClick={() => setShowNewModal(true)}
              >
                Create Session
              </Button>
            )}
          </Box>
        ) : (
          filteredSessions.map((session) => (
            <SessionCard
              key={session.id}
              session={session}
              isActive={session.id === currentSessionId}
              onClick={handleSessionClick}
              onEdit={handleEditSession}
              onDelete={handleDeleteSession}
            />
          ))
        )}
      </Box>

      {/* Error display */}
      {error && (
        <Typography variant="caption" color="error" sx={{ mt: 1 }}>
          {error}
        </Typography>
      )}

      {/* New session modal */}
      <NewSessionModal
        open={showNewModal}
        onClose={() => setShowNewModal(false)}
        onCreate={handleCreateSession}
      />
    </Box>
  )
}

export default SessionList
