type WebSocketCallback = (data: any) => void
type WebSocketErrorCallback = (error: Event) => void

interface WebSocketMessage {
  type: string
  data: any
  timestamp: string
}

class WebSocketService {
  private socket: WebSocket | null = null
  private url: string
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  private heartbeatInterval: number | null = null
  private heartbeatTimeout = 30000 // 30 seconds

  private messageCallbacks: Map<string, WebSocketCallback[]> = new Map()
  private errorCallbacks: WebSocketErrorCallback[] = []
  private openCallbacks: (() => void)[] = []
  private closeCallbacks: (() => void)[] = []

  constructor(baseURL: string = '') {
    this.url = baseURL
  }

  connect(sessionId: string): void {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      return
    }

    const wsUrl = `${this.url.replace('http', 'ws')}/ws/v1/chat/${sessionId}`
    this.socket = new WebSocket(wsUrl)

    this.socket.onopen = () => {
      console.log('WebSocket connection opened')
      this.reconnectAttempts = 0
      this.startHeartbeat()
      this.openCallbacks.forEach(callback => callback())
    }

    this.socket.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data)

        // Handle heartbeat
        if (message.type === 'heartbeat') {
          return
        }

        // Call type-specific callbacks
        const callbacks = this.messageCallbacks.get(message.type) || []
        callbacks.forEach(callback => callback(message.data))

        // Call wildcard callbacks
        const wildcardCallbacks = this.messageCallbacks.get('*') || []
        wildcardCallbacks.forEach(callback => callback(message))
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error)
      }
    }

    this.socket.onerror = (error) => {
      console.error('WebSocket error:', error)
      this.errorCallbacks.forEach(callback => callback(error))
    }

    this.socket.onclose = (event) => {
      console.log('WebSocket connection closed:', event.code, event.reason)
      this.stopHeartbeat()
      this.closeCallbacks.forEach(callback => callback())

      // Attempt reconnection if not normal closure
      if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
        setTimeout(() => {
          this.reconnectAttempts++
          this.connect(sessionId)
        }, this.reconnectDelay * Math.pow(2, this.reconnectAttempts))
      }
    }
  }

  disconnect(): void {
    this.stopHeartbeat()

    if (this.socket) {
      this.socket.close(1000, 'Client disconnect')
      this.socket = null
    }
  }

  send(type: string, data: any): boolean {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      console.error('WebSocket is not connected')
      return false
    }

    try {
      const message: WebSocketMessage = {
        type,
        data,
        timestamp: new Date().toISOString(),
      }
      this.socket.send(JSON.stringify(message))
      return true
    } catch (error) {
      console.error('Failed to send WebSocket message:', error)
      return false
    }
  }

  private startHeartbeat(): void {
    this.heartbeatInterval = window.setInterval(() => {
      this.send('heartbeat', { timestamp: Date.now() })
    }, 15000) // Send heartbeat every 15 seconds
  }

  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval)
      this.heartbeatInterval = null
    }
  }

  // Event subscription methods
  on(type: string, callback: WebSocketCallback): void {
    if (!this.messageCallbacks.has(type)) {
      this.messageCallbacks.set(type, [])
    }
    this.messageCallbacks.get(type)!.push(callback)
  }

  off(type: string, callback: WebSocketCallback): void {
    const callbacks = this.messageCallbacks.get(type)
    if (callbacks) {
      this.messageCallbacks.set(
        type,
        callbacks.filter(cb => cb !== callback)
      )
    }
  }

  onError(callback: WebSocketErrorCallback): void {
    this.errorCallbacks.push(callback)
  }

  onOpen(callback: () => void): void {
    this.openCallbacks.push(callback)
  }

  onClose(callback: () => void): void {
    this.closeCallbacks.push(callback)
  }

  // Utility methods
  isConnected(): boolean {
    return this.socket !== null && this.socket.readyState === WebSocket.OPEN
  }

  getReadyState(): number {
    return this.socket ? this.socket.readyState : WebSocket.CLOSED
  }

  getReconnectAttempts(): number {
    return this.reconnectAttempts
  }

  resetReconnectAttempts(): void {
    this.reconnectAttempts = 0
  }
}

// Create singleton instance
const websocketService = new WebSocketService(import.meta.env.VITE_API_BASE_URL || '')

export default websocketService