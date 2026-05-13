/**
 * SSE (Server-Sent Events) 工具函数
 */

import { SSEEvent } from '@/types/chat'

export interface SSEClientOptions {
  url: string
  headers?: Record<string, string>
  withCredentials?: boolean
  reconnectInterval?: number
  maxReconnectAttempts?: number
  onOpen?: () => void
  onMessage?: (event: SSEEvent) => void
  onError?: (error: Event) => void
  onClose?: () => void
  heartbeatTimeout?: number
}

export class SSEClient {
  private url: string
  private headers: Record<string, string>
  private withCredentials: boolean
  private reconnectInterval: number
  private maxReconnectAttempts: number
  private onOpen?: () => void
  private onMessage?: (event: SSEEvent) => void
  private onError?: (error: Event) => void
  private onClose?: () => void
  private heartbeatTimeout: number

  private eventSource: EventSource | null = null
  private reconnectAttempts: number = 0
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private heartbeatTimer: ReturnType<typeof setTimeout> | null = null
  private isConnected: boolean = false
  private isManuallyClosed: boolean = false

  constructor(options: SSEClientOptions) {
    this.url = options.url
    this.headers = options.headers || {}
    this.withCredentials = options.withCredentials || false
    this.reconnectInterval = options.reconnectInterval || 3000
    this.maxReconnectAttempts = options.maxReconnectAttempts || 10
    this.onOpen = options.onOpen
    this.onMessage = options.onMessage
    this.onError = options.onError
    this.onClose = options.onClose
    this.heartbeatTimeout = options.heartbeatTimeout || 45000
  }

  connect(): void {
    if (this.isConnected || this.eventSource) {
      return
    }

    this.isManuallyClosed = false

    try {
      // Build URL with query params from headers
      const url = new URL(this.url, window.location.origin)
      Object.entries(this.headers).forEach(([key, value]) => {
        url.searchParams.set(key, value)
      })

      this.eventSource = new EventSource(url.toString(), {
        withCredentials: this.withCredentials,
      })

      this.eventSource.onopen = () => {
        this.isConnected = true
        this.reconnectAttempts = 0
        this.resetHeartbeat()
        this.onOpen?.()
      }

      this.eventSource.onmessage = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data)
          const sseEvent: SSEEvent = {
            event: data.event || 'message',
            data: data,
          }
          this.resetHeartbeat()
          this.onMessage?.(sseEvent)
        } catch {
          // Non-JSON data (e.g., plain text heartbeat)
          if (event.data === 'ping' || event.data.includes('heartbeat')) {
            this.resetHeartbeat()
            return
          }
          this.onMessage?.({ event: 'message', data: event.data })
        }
      }

      this.eventSource.addEventListener('heartbeat', () => {
        this.resetHeartbeat()
      })

      this.eventSource.addEventListener('error', (event: Event) => {
        // Check if it's a ping/heartbeat event
        if (event.type === 'ping') {
          this.resetHeartbeat()
          return
        }

        console.warn('SSE error event:', event)
        this.onError?.(event)

        // Auto-reconnect on error
        if (!this.isManuallyClosed) {
          this.handleReconnect()
        }
      })

      this.eventSource.onerror = (event: Event) => {
        console.error('SSE connection error:', event)

        // Only trigger reconnect if not manually closed
        if (!this.isManuallyClosed) {
          this.isConnected = false
          this.cleanup()
          this.handleReconnect()
        }

        this.onError?.(event)
      }
    } catch (error) {
      console.error('Failed to create EventSource:', error)
      if (!this.isManuallyClosed) {
        this.handleReconnect()
      }
    }
  }

  disconnect(): void {
    this.isManuallyClosed = true
    this.isConnected = false
    this.cleanup()
    this.onClose?.()
  }

  private cleanup(): void {
    if (this.eventSource) {
      this.eventSource.close()
      this.eventSource = null
    }
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.heartbeatTimer) {
      clearTimeout(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  private handleReconnect(): void {
    if (this.isManuallyClosed) return
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max SSE reconnect attempts reached')
      this.onError?.(new Event('max_reconnect'))
      return
    }

    this.reconnectAttempts++
    const delay = this.calculateBackoff(this.reconnectAttempts)

    console.log(`SSE reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`)

    this.reconnectTimer = setTimeout(() => {
      this.connect()
    }, delay)
  }

  private calculateBackoff(attempt: number): number {
    const base = this.reconnectInterval
    const max = 30000 // 30 seconds max
    const backoff = Math.min(base * Math.pow(1.5, attempt - 1), max)
    // Add jitter (±15%)
    const jitter = backoff * 0.15 * (Math.random() * 2 - 1)
    return Math.round(backoff + jitter)
  }

  private resetHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearTimeout(this.heartbeatTimer)
    }
    this.heartbeatTimer = setTimeout(() => {
      console.warn('SSE heartbeat timeout, reconnecting...')
      this.isConnected = false
      this.cleanup()
      this.handleReconnect()
    }, this.heartbeatTimeout)
  }

  getReconnectAttempts(): number {
    return this.reconnectAttempts
  }

  getIsConnected(): boolean {
    return this.isConnected
  }
}

/**
 * 解析SSE原始数据流
 */
export function parseSSEData(rawData: string): SSEEvent[] {
  const events: SSEEvent[] = []
  const lines = rawData.split('\n')

  let currentEvent: Partial<SSEEvent> = {}
  let dataLines: string[] = []

  for (const line of lines) {
    if (line.startsWith('event:')) {
      currentEvent.event = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trim())
    } else if (line.startsWith('id:')) {
      // SSE id field, can be used for Last-Event-ID
    } else if (line.startsWith('retry:')) {
      currentEvent.retry = parseInt(line.slice(6).trim(), 10)
    } else if (line === '') {
      // Empty line = end of event
      if (dataLines.length > 0) {
        try {
          const data = JSON.parse(dataLines.join('\n'))
          events.push({
            event: currentEvent.event || 'message',
            data,
            retry: currentEvent.retry,
          })
        } catch {
          events.push({
            event: currentEvent.event || 'message',
            data: dataLines.join('\n'),
            retry: currentEvent.retry,
          })
        }
      }
      currentEvent = {}
      dataLines = []
    }
  }

  return events
}

/**
 * 创建SSE心跳检测器
 */
export function createHeartbeatMonitor(
  onTimeout: () => void,
  timeoutMs: number = 45000
): {
  heartbeat: () => void
  stop: () => void
} {
  let timer: ReturnType<typeof setTimeout> | null = null

  const reset = () => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(onTimeout, timeoutMs)
  }

  return {
    heartbeat: reset,
    stop: () => {
      if (timer) {
        clearTimeout(timer)
        timer = null
      }
    },
  }
}
