import { useEffect, useRef, useState, useCallback } from 'react'
import { SSEEvent } from '@/types/chat'
import sseService from '@/services/sseService'

interface UseSSEOptions {
  sessionId?: string
  autoConnect?: boolean
  onMessage?: (event: SSEEvent) => void
  onError?: (error: Event) => void
  onOpen?: () => void
  onClose?: () => void
}

export default function useSSE(options: UseSSEOptions = {}) {
  const {
    sessionId,
    autoConnect = true,
    onMessage,
    onError,
    onOpen,
    onClose,
  } = options

  const [isConnected, setIsConnected] = useState(false)
  const [reconnectAttempts, setReconnectAttempts] = useState(0)
  const [lastHeartbeat, setLastHeartbeat] = useState<Date | null>(null)
  const [error, setError] = useState<string | null>(null)

  const messageHandlerRef = useRef<(event: SSEEvent) => void>()
  const errorHandlerRef = useRef<(error: Event) => void>()
  const openHandlerRef = useRef<() => void>()
  const closeHandlerRef = useRef<() => void>()

  // Update handlers when they change
  useEffect(() => {
    messageHandlerRef.current = onMessage
    errorHandlerRef.current = onError
    openHandlerRef.current = onOpen
    closeHandlerRef.current = onClose
  }, [onMessage, onError, onOpen, onClose])

  // Setup SSE event handlers
  useEffect(() => {
    const handleMessage = (event: SSEEvent) => {
      if (event.event === 'heartbeat') {
        setLastHeartbeat(new Date())
        return
      }
      messageHandlerRef.current?.(event)
    }

    const handleError = (error: Event) => {
      setError('SSE connection error')
      errorHandlerRef.current?.(error)
    }

    const handleOpen = () => {
      setIsConnected(true)
      setError(null)
      openHandlerRef.current?.()
    }

    const handleClose = () => {
      setIsConnected(false)
      closeHandlerRef.current?.()
    }

    sseService.onMessage(handleMessage)
    sseService.onError(handleError)
    sseService.onOpen(handleOpen)
    sseService.onClose(handleClose)

    return () => {
      sseService.removeMessageCallback(handleMessage)
      sseService.removeErrorCallback(handleError)
      // Note: We can't remove open/close callbacks without exposing methods
    }
  }, [])

  // Auto-connect when sessionId changes
  useEffect(() => {
    if (autoConnect && sessionId) {
      connect(sessionId)
    }

    return () => {
      if (sessionId) {
        disconnect()
      }
    }
  }, [sessionId, autoConnect])

  const connect = useCallback((connectSessionId: string) => {
    sseService.connect(connectSessionId)
    setReconnectAttempts(sseService.getReconnectAttempts())
  }, [])

  const disconnect = useCallback(() => {
    sseService.disconnect()
  }, [])

  const send = useCallback((event: SSEEvent) => {
    // SSE is server-to-client only, cannot send messages
    // For bidirectional communication, use WebSocket
    console.warn('SSE is server-to-client only. Use WebSocket for sending messages.')
  }, [])

  // Check connection health
  useEffect(() => {
    if (!isConnected) return

    const interval = setInterval(() => {
      setReconnectAttempts(sseService.getReconnectAttempts())
    }, 5000)

    return () => clearInterval(interval)
  }, [isConnected])

  return {
    isConnected,
    reconnectAttempts,
    lastHeartbeat,
    error,
    connect,
    disconnect,
    send,
  }
}