import React, { memo } from 'react'
import {
  Box,
  Typography,
  Avatar,
  Paper,
  Chip,
  IconButton,
  Tooltip,
  Collapse,
} from '@mui/material'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
import RefreshIcon from '@mui/icons-material/Refresh'
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline'
import SmartToyIcon from '@mui/icons-material/SmartToy'
import PersonIcon from '@mui/icons-material/Person'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Message } from '@/types/chat'
import useUIStore from '@/stores/uiStore'

interface MessageBubbleProps {
  message: Message
  isLast?: boolean
  onRetry?: (messageId: string) => void
}

const MessageBubble: React.FC<MessageBubbleProps> = memo(({ message, isLast, onRetry }) => {
  const showTimestamps = useUIStore((s) => s.showTimestamps)
  const showAvatars = useUIStore((s) => s.showAvatars)
  const markdownRendering = useUIStore((s) => s.markdownRendering)
  const messageDensity = useUIStore((s) => s.messageDensity)

  const isUser = message.role === 'user'
  const isSystem = message.role === 'system'
  const isError = message.processing_status === 'failed'
  const isProcessing = message.processing_status === 'processing'
  const [expanded, setExpanded] = React.useState(false)

  const handleCopy = () => {
    if (message.content) {
      navigator.clipboard.writeText(message.content)
    }
  }

  const handleRetry = () => {
    onRetry?.(message.id)
  }

  const densityStyles = {
    compact: { py: 0.5, px: 1.5 },
    comfortable: { py: 1, px: 2 },
    spacious: { py: 1.5, px: 2.5 },
  }

  const padding = densityStyles[messageDensity] || densityStyles.comfortable

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp)
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: isUser ? 'flex-end' : 'flex-start',
        mb: messageDensity === 'compact' ? 0.5 : 1.5,
        maxWidth: '85%',
        alignSelf: isUser ? 'flex-end' : 'flex-start',
      }}
    >
      {/* Sender info */}
      {showAvatars && !isUser && (
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 0.5, ml: 1 }}>
          <Avatar sx={{ width: 24, height: 24, mr: 0.5, bgcolor: isError ? 'error.main' : 'primary.main' }}>
            {isSystem ? <SmartToyIcon sx={{ fontSize: 16 }} /> : <SmartToyIcon sx={{ fontSize: 16 }} />}
          </Avatar>
          <Typography variant="caption" color="text.secondary" fontWeight="medium">
            {message.metadata?.agent_id || 'Assistant'}
          </Typography>
          {message.intent && (
            <Chip
              label={message.intent}
              size="small"
              variant="outlined"
              sx={{ ml: 1, height: 18, fontSize: '0.65rem' }}
            />
          )}
        </Box>
      )}

      {/* Message bubble */}
      <Paper
        elevation={0}
        sx={{
          ...padding,
          borderRadius: 2,
          bgcolor: isUser ? 'primary.main' : isError ? 'error.light' : isSystem ? 'grey.100' : 'background.paper',
          color: isUser ? 'primary.contrastText' : isError ? 'error.contrastText' : 'text.primary',
          border: isUser ? 'none' : '1px solid',
          borderColor: isError ? 'error.main' : 'divider',
          position: 'relative',
          maxWidth: '100%',
          wordBreak: 'break-word',
          opacity: isProcessing ? 0.7 : 1,
        }}
      >
        {/* Error indicator */}
        {isError && (
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 0.5 }}>
            <ErrorOutlineIcon fontSize="small" sx={{ mr: 0.5 }} />
            <Typography variant="caption" fontWeight="bold">
              Error
            </Typography>
          </Box>
        )}

        {/* Message content */}
        {message.content ? (
          markdownRendering && !isUser ? (
            <Box sx={{ '& p': { my: 0.5 }, '& pre': { borderRadius: 1, p: 1, overflow: 'auto' } }}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
            </Box>
          ) : (
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
              {message.content}
            </Typography>
          )
        ) : (
          <Typography variant="body2" color="text.secondary" fontStyle="italic">
            {isProcessing ? 'Thinking...' : '(empty)'}
          </Typography>
        )}

        {/* Tool calls indicator */}
        {message.tool_calls && message.tool_calls.length > 0 && (
          <Box sx={{ mt: 0.5 }}>
            <Chip
              label={`${message.tool_calls.length} tool call${message.tool_calls.length > 1 ? 's' : ''}`}
              size="small"
              variant="outlined"
              onClick={() => setExpanded(!expanded)}
              sx={{ cursor: 'pointer', fontSize: '0.7rem', height: 20 }}
            />
            <Collapse in={expanded}>
              <Box sx={{ mt: 0.5, fontSize: '0.75rem' }}>
                {message.tool_calls.map((tc) => (
                  <Typography key={tc.id} variant="caption" display="block" color="text.secondary">
                    → {tc.function.name}({JSON.stringify(tc.function.arguments).slice(0, 80)})
                  </Typography>
                ))}
              </Box>
            </Collapse>
          </Box>
        )}

        {/* Tool results */}
        {message.tool_results && message.tool_results.length > 0 && (
          <Box sx={{ mt: 0.5 }}>
            {message.tool_results.map((tr) => (
              <Chip
                key={tr.tool_call_id}
                label={tr.is_error ? 'Tool error' : 'Tool result'}
                size="small"
                color={tr.is_error ? 'error' : 'success'}
                variant="outlined"
                sx={{ mr: 0.5, mb: 0.5, fontSize: '0.7rem', height: 20 }}
              />
            ))}
          </Box>
        )}

        {/* Timestamp */}
        {showTimestamps && (
          <Typography
            variant="caption"
            sx={{
              display: 'block',
              mt: 0.25,
              opacity: 0.6,
              textAlign: 'right',
              fontSize: '0.65rem',
            }}
          >
            {formatTime(message.created_at)}
          </Typography>
        )}
      </Paper>

      {/* Action buttons */}
      {!isUser && message.content && !isProcessing && (
        <Box sx={{ display: 'flex', gap: 0.5, mt: 0.25, ml: 1 }}>
          <Tooltip title="Copy">
            <IconButton size="small" onClick={handleCopy} sx={{ opacity: 0.5, '&:hover': { opacity: 1 } }}>
              <ContentCopyIcon sx={{ fontSize: 14 }} />
            </IconButton>
          </Tooltip>
          {isError && onRetry && (
            <Tooltip title="Retry">
              <IconButton size="small" onClick={handleRetry} sx={{ opacity: 0.5, '&:hover': { opacity: 1 } }}>
                <RefreshIcon sx={{ fontSize: 14 }} />
              </IconButton>
            </Tooltip>
          )}
        </Box>
      )}
    </Box>
  )
})

MessageBubble.displayName = 'MessageBubble'

export default MessageBubble
