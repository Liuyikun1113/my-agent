import React, { useEffect, useCallback, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Box,
  TextField,
  IconButton,
  Typography,
  Paper,
  Tooltip,
  Divider,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Chip,
} from '@mui/material'
import SendIcon from '@mui/icons-material/Send'
import StopIcon from '@mui/icons-material/Stop'
import AttachFileIcon from '@mui/icons-material/AttachFile'
import MoreVertIcon from '@mui/icons-material/MoreVert'
import ClearAllIcon from '@mui/icons-material/ClearAll'
import DownloadIcon from '@mui/icons-material/Download'
import useChatStore from '@/stores/chatStore'
import useSessionStore from '@/stores/sessionStore'
import useAgentStore from '@/stores/agentStore'
import useUIStore from '@/stores/uiStore'
import MessageList from './MessageList'
import TypingIndicator from './TypingIndicator'

const ChatWindow: React.FC = () => {
  const { sessionId: paramSessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)

  const sessionId = paramSessionId || useSessionStore((s) => s.currentSessionId)
  const session = useSessionStore((s) => sessionId ? s.getSessionById(sessionId) : null)

  const {
    messages: allMessages,
    streamingMessage,
    isStreaming,
    isLoading,
    error: chatError,
    sendMessage,
    fetchMessages,
    clearMessages,
    connectSSE,
    disconnectSSE,
    getMessages,
  } = useChatStore()

  const agents = useAgentStore((s) => s.agents)
  const agentStatus = useAgentStore((s) => s.agentStatus)
  const chatLayout = useUIStore((s) => s.chatLayout)

  const [input, setInput] = useState('')
  const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null)
  const [sending, setSending] = useState(false)

  const sessionMessages = sessionId ? getMessages(sessionId) : []

  // Load messages on mount
  useEffect(() => {
    if (sessionId) {
      fetchMessages(sessionId).catch(console.error)
      connectSSE(sessionId)
    }
    return () => {
      disconnectSSE()
    }
  }, [sessionId])

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [sessionId])

  const handleSend = useCallback(async () => {
    const content = input.trim()
    if (!content || !sessionId || sending) return

    setSending(true)
    setInput('')

    try {
      await sendMessage(sessionId, content)
    } catch (err) {
      console.error('Failed to send:', err)
    } finally {
      setSending(false)
      inputRef.current?.focus()
    }
  }, [input, sessionId, sending, sendMessage])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSend()
      }
    },
    [handleSend]
  )

  const handleClear = useCallback(() => {
    if (sessionId) {
      clearMessages(sessionId)
    }
    setMenuAnchor(null)
  }, [sessionId, clearMessages])

  const handleRetry = useCallback(
    (messageId: string) => {
      // Find the original user message before this failed message
      const msgs = sessionMessages
      const idx = msgs.findIndex((m) => m.id === messageId)
      if (idx > 0) {
        const prevUserMsg = [...msgs].slice(0, idx).reverse().find((m) => m.role === 'user')
        if (prevUserMsg?.content) {
          sendMessage(sessionId!, prevUserMsg.content, true)
        }
      }
    },
    [sessionMessages, sessionId, sendMessage]
  )

  // Get active agent for this session
  const activeAgent = agents.length > 0 ? agents[0] : null
  const activeAgentStatus = activeAgent ? agentStatus[activeAgent.id] : null

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        overflow: 'hidden',
      }}
    >
      {/* Chat header */}
      <Paper
        elevation={0}
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 2,
          py: 1,
          borderBottom: 1,
          borderColor: 'divider',
          borderRadius: 0,
          bgcolor: 'background.paper',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="subtitle1" fontWeight="bold" noWrap sx={{ maxWidth: 300 }}>
            {session?.title || `Chat ${sessionId?.slice(0, 8) || ''}`}
          </Typography>
          {activeAgent && (
            <Chip
              label={activeAgent.name}
              size="small"
              color={activeAgentStatus?.status === 'busy' ? 'warning' : 'primary'}
              variant="outlined"
              sx={{ height: 24 }}
            />
          )}
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Typography variant="caption" color="text.secondary">
            {sessionMessages.length} message{sessionMessages.length !== 1 ? 's' : ''}
          </Typography>
          <IconButton size="small" onClick={(e) => setMenuAnchor(e.currentTarget)}>
            <MoreVertIcon fontSize="small" />
          </IconButton>
          <Menu
            anchorEl={menuAnchor}
            open={Boolean(menuAnchor)}
            onClose={() => setMenuAnchor(null)}
          >
            <MenuItem onClick={handleClear}>
              <ListItemIcon>
                <ClearAllIcon fontSize="small" />
              </ListItemIcon>
              <ListItemText>Clear messages</ListItemText>
            </MenuItem>
            <MenuItem onClick={() => setMenuAnchor(null)}>
              <ListItemIcon>
                <DownloadIcon fontSize="small" />
              </ListItemIcon>
              <ListItemText>Export chat</ListItemText>
            </MenuItem>
          </Menu>
        </Box>
      </Paper>

      {/* Messages area */}
      <Box
        sx={{
          flex: 1,
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          bgcolor: 'grey.50',
        }}
      >
        <MessageList
          messages={sessionMessages}
          streamingMessage={streamingMessage}
          isStreaming={isStreaming}
          onRetry={handleRetry}
          emptyText={chatLayout === 'focus' ? 'Start a focused conversation' : 'No messages yet. Start a conversation!'}
        />
      </Box>

      {/* Error banner */}
      {chatError && (
        <Paper
          sx={{
            mx: 2,
            p: 1,
            bgcolor: 'error.light',
            color: 'error.contrastText',
            borderRadius: 1,
          }}
        >
          <Typography variant="caption">{chatError}</Typography>
        </Paper>
      )}

      {/* Input area */}
      <Paper
        elevation={3}
        sx={{
          display: 'flex',
          alignItems: 'flex-end',
          gap: 1,
          p: 2,
          borderTop: 1,
          borderColor: 'divider',
          borderRadius: 0,
          bgcolor: 'background.paper',
        }}
      >
        <Tooltip title="Attach file">
          <IconButton size="small" sx={{ mb: 0.5 }}>
            <AttachFileIcon />
          </IconButton>
        </Tooltip>

        <TextField
          inputRef={inputRef}
          fullWidth
          multiline
          maxRows={6}
          minRows={1}
          placeholder={sessionId ? 'Type your message... (Enter to send, Shift+Enter for new line)' : 'Select a session to start chatting'}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={!sessionId || isLoading}
          variant="outlined"
          size="small"
          sx={{
            '& .MuiOutlinedInput-root': {
              borderRadius: 3,
              bgcolor: 'grey.50',
            },
          }}
        />

        {isStreaming ? (
          <Tooltip title="Stop generating">
            <IconButton color="error" onClick={() => disconnectSSE()} sx={{ mb: 0.5 }}>
              <StopIcon />
            </IconButton>
          </Tooltip>
        ) : (
          <Tooltip title="Send message">
            <span>
              <IconButton
                color="primary"
                onClick={handleSend}
                disabled={!input.trim() || !sessionId || sending}
                sx={{ mb: 0.5 }}
              >
                <SendIcon />
              </IconButton>
            </span>
          </Tooltip>
        )}
      </Paper>
    </Box>
  )
}

export default ChatWindow
