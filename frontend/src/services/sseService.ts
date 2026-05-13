import { SSEEvent } from '@/types/chat'

type SSECallback = (event: SSEEvent) => void
type SSEErrorCallback = (error: Event) => void

class SSEService {
  private eventSource: EventSource | null = null
  private url: string
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  private heartbeatInterval: number | null = null
  private lastHeartbeat: number = Date.now()
  private heartbeatTimeout = 45000 // 45 seconds (slightly longer than server's 30s)

  private messageCallbacks: SSECallback[] = []
  private errorCallbacks: SSEErrorCallback[] = []
  private openCallbacks: (() => void)[] = []
  private closeCallbacks: (() => void)[] = []

  constructor(baseURL: string = '') {
    this.url = baseURL
  }

  connect(sessionId: string): void {
    if (this.eventSource) {
      this.disconnect()
    }

    const sseUrl = `${this.url}/sse/v1/connect?session_id=${sessionId}`
    this.eventSource = new EventSource(sseUrl)

    this.eventSource.onopen = () => {
      console.log('SSE connection opened')
      this.reconnectAttempts = 0
      this.startHeartbeatCheck()
      this.openCallbacks.forEach(callback => callback())
    }

    this.eventSource.onmessage = (event) => {
      try {
        const sseEvent: SSEEvent = JSON.parse(event.data)

        if (sseEvent.event === 'heartbeat') {
          this.lastHeartbeat = Date.now()
          return
        }

        this.messageCallbacks.forEach(callback => callback(sseEvent))
      } catch (error) {
        console.error('Failed to parse SSE event:', error)
      }
    }

    this.eventSource.onerror = (error) => {
      console.error('SSE connection error:', error)
      this.errorCallbacks.forEach(callback => callback(error))
      this.disconnect()

      // Attempt reconnection
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        setTimeout(() => {
          this.reconnectAttempts++
          this.connect(sessionId)
        }, this.reconnectDelay * Math.pow(2, this.reconnectAttempts))
      }
    }
  }

  disconnect(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval)
      this.heartbeatInterval = null
    }

    if (this.eventSource) {
      this.eventSource.close()
      this.eventSource = null
      this.closeCallbacks.forEach(callback => callback())
    }
  }

  private startHeartbeatCheck(): void {
    this.lastHeartbeat = Date.now()

    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval)
    }

    this.heartbeatInterval = window.setInterval(() => {
      const timeSinceLastHeartbeat = Date.now() - this.lastHeartbeat

      if (timeSinceLastHeartbeat > this.heartbeatTimeout) {
        console.warn('SSE heartbeat timeout, reconnecting...')
        this.disconnect()

        // Attempt to reconnect
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++
          // We need to know the session ID to reconnect
          // This is a limitation - we should store the session ID
          console.error('Cannot reconnect without session ID')
        }
      }
    }, 10000) // Check every 10 seconds
  }

  // Event subscription methods
  onMessage(callback: SSECallback): void {
    this.messageCallbacks.push(callback)
  }

  onError(callback: SSEErrorCallback): void {
    this.errorCallbacks.push(callback)
  }

  onOpen(callback: () => void): void {
    this.openCallbacks.push(callback)
  }

  onClose(callback: () => void): void {
    this.closeCallbacks.push(callback)
  }

  removeMessageCallback(callback: SSECallback): void {
    this.messageCallbacks = this.messageCallbacks.filter(cb => cb !== callback)
  }

  removeErrorCallback(callback: SSEErrorCallback): void {
    this.errorCallbacks = this.errorCallbacks.filter(cb => cb !== callback)
  }

  // Utility methods
  isConnected(): boolean {
    return this.eventSource !== null && this.eventSource.readyState === EventSource.OPEN
  }

  getReconnectAttempts(): number {
    return this.reconnectAttempts
  }

  resetReconnectAttempts(): void {
    this.reconnectAttempts = 0
  }
}

// Create singleton instance
const sseService = new SSEService(import.meta.env.VITE_API_BASE_URL || '')

export default sseService