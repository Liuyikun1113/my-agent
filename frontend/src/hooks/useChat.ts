import { useState, useCallback, useEffect } from 'react'
import useChatStore from '@/stores/chatStore'
import useSessionStore from '@/stores/sessionStore'
import { Message } from '@/types/chat'
import useSSE from './useSSE'

interface UseChatOptions {
  sessionId?: string
  autoConnectSSE?: boolean
  onNewMessage?: (message: Message) => void
  onStreamingComplete?: (message: Message) => void
}

export default function useChat(options: UseChatOptions = {}) {
  const {
    sessionId: propSessionId,
    autoConnectSSE = true,
    onNewMessage,
    onStreamingComplete,
  } = options

  // Get current session from store if not provided
  const storeSessionId = useSessionStore((state) => state.currentSessionId)
  const sessionId = propSessionId || storeSessionId

  // Get chat store actions and state
  const {
    messages,
    streamingMessage,
    isStreaming,
    isLoading,
    error,
    sendMessage: storeSendMessage,
    fetchMessages: storeFetchMessages,
    clearMessages: storeClearMessages,
    connectSSE: storeConnectSSE,
    disconnectSSE: storeDisconnectSSE,
    getMessages: storeGetMessages,
    getLastMessage: storeGetLastMessage,
  } = useChatStore()

  // Local state
  const [input, setInput] = useState('')
  const [isTyping, setIsTyping] = useState(false)

  // SSE connection
  const sse = useSSE({
    sessionId,
    autoConnect: autoConnectSSE,
    onMessage: (event) => {
      if (event.event === 'message') {
        const message = event.data as Message
        onNewMessage?.(message)
      }
    },
  })

  // Get messages for current session
  const sessionMessages = sessionId ? storeGetMessages(sessionId) : []

  // Load messages when session changes
  useEffect(() => {
    if (sessionId) {
      storeFetchMessages(sessionId).catch(console.error)
    }
  }, [sessionId])

  // Connect SSE when session changes
  useEffect(() => {
    if (sessionId && autoConnectSSE) {
      storeConnectSSE(sessionId)
    }

    return () => {
      if (sessionId) {
        storeDisconnectSSE()
      }
    }
  }, [sessionId, autoConnectSSE])

  // Handle streaming completion
  useEffect(() => {
    if (streamingMessage && !isStreaming && onStreamingComplete) {
      onStreamingComplete(streamingMessage)
    }
  }, [streamingMessage, isStreaming, onStreamingComplete])

  // Send message handler
  const sendMessage = useCallback(
    async (content: string) => {
      if (!sessionId || !content.trim()) {
        return null
      }

      try {
        const message = await storeSendMessage(sessionId, content)
        setInput('')
        return message
      } catch (error) {
        console.error('Failed to send message:', error)
        throw error
      }
    },
    [sessionId, storeSendMessage]
  )

  // Send current input
  const sendCurrentMessage = useCallback(
    () => {
      if (!input.trim()) return
      return sendMessage(input)
    },
    [input, sendMessage]
  )

  // Handle input change
  const handleInputChange = useCallback((value: string) => {
    setInput(value)
  }, [])

  // Clear chat
  const clearChat = useCallback(() => {
    if (sessionId) {
      storeClearMessages(sessionId)
    }
  }, [sessionId, storeClearMessages])

  // Simulate typing indicator
  const simulateTyping = useCallback((duration = 1000) => {
    setIsTyping(true)
    setTimeout(() => setIsTyping(false), duration)
  }, [])

  return {
    // State
    sessionId,
    messages: sessionMessages,
    streamingMessage,
    isStreaming,
    isLoading,
    error,
    input,
    isTyping,
    lastMessage: sessionId ? storeGetLastMessage(sessionId) : null,

    // Actions
    sendMessage,
    sendCurrentMessage,
    handleInputChange,
    setInput,
    clearChat,
    fetchMessages: () => sessionId ? storeFetchMessages(sessionId) : Promise.resolve([]),
    simulateTyping,

    // SSE
    isSSEConnected: sse.isConnected,
    sseReconnectAttempts: sse.reconnectAttempts,
    connectSSE: storeConnectSSE,
    disconnectSSE: storeDisconnectSSE,

    // UI helpers
    canSend: !!sessionId && !!input.trim() && !isLoading && !isStreaming,
    hasMessages: sessionMessages.length > 0,
  }
}