import React, { useRef, useEffect, useCallback } from 'react'
import { Box, Typography, Divider } from '@mui/material'
import { Message } from '@/types/chat'
import useUIStore from '@/stores/uiStore'
import MessageBubble from './MessageBubble'
import TypingIndicator from './TypingIndicator'

interface MessageListProps {
  messages: Message[]
  streamingMessage?: Message | null
  isStreaming?: boolean
  onRetry?: (messageId: string) => void
  emptyText?: string
}

const MessageList: React.FC<MessageListProps> = ({
  messages,
  streamingMessage,
  isStreaming,
  onRetry,
  emptyText = 'No messages yet. Start a conversation!',
}) => {
  const autoScroll = useUIStore((s) => s.autoScroll)
  const chatLayout = useUIStore((s) => s.chatLayout)
  const bottomRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = useCallback((smooth = true) => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({
        behavior: smooth ? 'smooth' : 'auto',
        block: 'end',
      })
    }
  }, [])

  // Auto-scroll on new messages
  useEffect(() => {
    if (autoScroll) {
      scrollToBottom()
    }
  }, [messages, streamingMessage?.content, autoScroll, scrollToBottom])

  // Group messages by date for dividers
  const groupedMessages = React.useMemo(() => {
    const groups: { date: string; messages: Message[] }[] = []

    messages.forEach((msg) => {
      const date = new Date(msg.created_at).toLocaleDateString()
      const lastGroup = groups[groups.length - 1]

      if (lastGroup && lastGroup.date === date) {
        lastGroup.messages.push(msg)
      } else {
        groups.push({ date, messages: [msg] })
      }
    })

    return groups
  }, [messages])

  const formatDateDivider = (dateStr: string) => {
    const date = new Date(dateStr)
    const today = new Date()
    const yesterday = new Date(today)
    yesterday.setDate(yesterday.getDate() - 1)

    if (date.toDateString() === today.toDateString()) return 'Today'
    if (date.toDateString() === yesterday.toDateString()) return 'Yesterday'
    return date.toLocaleDateString(undefined, {
      weekday: 'long',
      month: 'short',
      day: 'numeric',
    })
  }

  if (messages.length === 0 && !streamingMessage) {
    return (
      <Box
        sx={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'column',
          p: 4,
          gap: 2,
        }}
      >
        <Typography variant="h6" color="text.secondary">
          {emptyText}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Type a message below to begin
        </Typography>
      </Box>
    )
  }

  return (
    <Box
      ref={containerRef}
      sx={{
        flex: 1,
        overflow: 'auto',
        px: 2,
        py: chatLayout === 'focus' ? 4 : 2,
        display: 'flex',
        flexDirection: 'column',
        gap: 0,
      }}
    >
      {groupedMessages.map((group) => (
        <React.Fragment key={group.date}>
          {/* Date divider */}
          <Divider sx={{ my: 2 }}>
            <Typography variant="caption" color="text.secondary" sx={{ px: 1 }}>
              {formatDateDivider(group.date)}
            </Typography>
          </Divider>

          {group.messages.map((message, idx) => (
            <MessageBubble
              key={message.id}
              message={message}
              isLast={idx === group.messages.length - 1}
              onRetry={onRetry}
            />
          ))}
        </React.Fragment>
      ))}

      {/* Streaming message */}
      {streamingMessage && (
        <MessageBubble
          message={streamingMessage}
          isLast={true}
        />
      )}

      {/* Typing indicator */}
      {isStreaming && (
        <Box sx={{ mt: 1, ml: 2 }}>
          <TypingIndicator />
        </Box>
      )}

      {/* Scroll anchor */}
      <div ref={bottomRef} />
    </Box>
  )
}

export default MessageList
