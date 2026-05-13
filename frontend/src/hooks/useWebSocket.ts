import { useEffect, useRef, useState, useCallback } from 'react'
import websocketService from '@/services/websocketService'

interface UseWebSocketOptions {
  sessionId?: string
  autoConnect?: boolean
  onMessage?: (type: string, data: any) => void
  onError?: (error: Event) => void
  onOpen?: () => void
  onClose?: () => void
  reconnect?: boolean
}

export default function useWebSocket(options: UseWebSocketOptions = {}) {
  const {
    sessionId,
    autoConnect = true,
    onMessage,
    onError,
    onOpen,
    onClose,
    reconnect = true,
  } = options

  const [isConnected, setIsConnected] = useState(false)
  const [reconnectAttempts, setReconnectAttempts] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const messageHandlerRef = useRef<(type: string, data: any) => void>()
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

  // Setup WebSocket event handlers
  useEffect(() => {
    const handleMessage = (type: string, data: any) => {
      messageHandlerRef.current?.(type, data)
    }

    const handleError = (error: Event) => {
      setError('WebSocket connection error')
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

    // Register wildcard handler for all message types
    websocketService.on('*', handleMessage)
    websocketService.onError(handleError)
    websocketService.onOpen(handleOpen)
    websocketService.onClose(handleClose)

    return () => {
      websocketService.off('*', handleMessage)
      // Note: We can't remove error/open/close callbacks without exposing methods
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
    websocketService.connect(connectSessionId)
    setReconnectAttempts(websocketService.getReconnectAttempts())
  }, [])

  const disconnect = useCallback(() => {
    websocketService.disconnect()
  }, [])

  const send = useCallback((type: string, data: any) => {
    return websocketService.send(type, data)
  }, [])

  const subscribe = useCallback((type: string, callback: (data: any) => void) => {
    websocketService.on(type, callback)
  }, [])

  const unsubscribe = useCallback((type: string, callback: (data: any) => void) => {
    websocketService.off(type, callback)
  }, [])

  // Monitor connection status
  useEffect(() => {
    if (!isConnected) return

    const interval = setInterval(() => {
      setReconnectAttempts(websocketService.getReconnectAttempts())
      setIsConnected(websocketService.isConnected())
    }, 5000)

    return () => clearInterval(interval)
  }, [isConnected])

  return {
    isConnected,
    reconnectAttempts,
    error,
    connect,
    disconnect,
    send,
    subscribe,
    unsubscribe,
    readyState: websocketService.getReadyState(),
  }
}