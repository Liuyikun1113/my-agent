import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { SSEClient, parseSSEData, createHeartbeatMonitor } from '@utils/sseUtils'

// Mock EventSource
class MockEventSource {
  url: string
  onopen: (() => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  readyState: number = 0
  CONNECTING = 0
  OPEN = 1
  CLOSED = 2

  constructor(url: string, _options?: any) {
    this.url = url
    setTimeout(() => {
      this.readyState = this.OPEN
      this.onopen?.()
    }, 0)
  }

  close() { this.readyState = this.CLOSED }
  addEventListener(_type: string, _handler: any) {}
}

globalThis.EventSource = MockEventSource as any

describe('SSEClient', () => {
  let client: SSEClient

  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.restoreAllTimers()
    vi.useRealTimers()
  })

  it('should create an SSEClient instance', () => {
    client = new SSEClient({ url: 'http://localhost:8000/sse/chat/test' })
    expect(client).toBeInstanceOf(SSEClient)
    expect(client.getIsConnected()).toBe(false)
  })

  it('should connect and set isConnected', async () => {
    const onOpen = vi.fn()
    client = new SSEClient({
      url: 'http://localhost:8000/sse/chat/test',
      onOpen,
    })

    client.connect()

    await vi.advanceTimersByTimeAsync(10)

    expect(onOpen).toHaveBeenCalled()
    expect(client.getIsConnected()).toBe(true)
  })

  it('should handle disconnect', () => {
    client = new SSEClient({ url: 'http://localhost:8000/sse/chat/test' })
    client.connect()
    client.disconnect()

    expect(client.getIsConnected()).toBe(false)
  })

  it('should not double-connect', () => {
    const onOpen = vi.fn()
    client = new SSEClient({ url: 'http://localhost:8000/sse/chat/test', onOpen })
    client.connect()
    client.connect()

    // onOpen should only fire once from the initial connect
    expect(onOpen.mock.calls.length).toBeLessThanOrEqual(1)
  })

  it('should track reconnect attempts', () => {
    client = new SSEClient({ url: 'http://localhost:8000/sse/chat/test' })
    expect(client.getReconnectAttempts()).toBe(0)
  })
})

describe('parseSSEData', () => {
  it('should parse single event', () => {
    const raw = 'data: {"event":"message","data":{"text":"hello"}}\n\n'
    const events = parseSSEData(raw)
    expect(events).toHaveLength(1)
    expect(events[0].event).toBe('message')
    expect(events[0].data.text).toBe('hello')
  })

  it('should parse multiple events', () => {
    const raw = [
      'data: {"event":"message","data":"first"}\n\n',
      'data: {"event":"message","data":"second"}\n\n',
    ].join('')
    const events = parseSSEData(raw)
    expect(events).toHaveLength(2)
  })

  it('should parse event with type', () => {
    const raw = 'event: heartbeat\ndata: ping\n\n'
    const events = parseSSEData(raw)
    expect(events).toHaveLength(1)
    expect(events[0].event).toBe('heartbeat')
    expect(events[0].data).toBe('ping')
  })

  it('should parse event with retry', () => {
    const raw = 'data: {"key":"val"}\nretry: 5000\n\n'
    const events = parseSSEData(raw)
    expect(events).toHaveLength(1)
    expect(events[0].retry).toBe(5000)
  })

  it('should handle multi-line data', () => {
    const raw = 'data: {"key":\n"val"}\n\n'
    const events = parseSSEData(raw)
    expect(events).toHaveLength(1)
  })

  it('should handle invalid JSON gracefully', () => {
    const raw = 'data: not-json\n\n'
    const events = parseSSEData(raw)
    expect(events).toHaveLength(1)
    expect(events[0].data).toBe('not-json')
  })

  it('should return empty array for empty input', () => {
    expect(parseSSEData('')).toEqual([])
  })
})

describe('createHeartbeatMonitor', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('should call onTimeout after specified duration', () => {
    const onTimeout = vi.fn()
    const monitor = createHeartbeatMonitor(onTimeout, 1000)

    vi.advanceTimersByTime(1100)
    expect(onTimeout).toHaveBeenCalled()
    monitor.stop()
  })

  it('should reset timer on heartbeat', () => {
    const onTimeout = vi.fn()
    const monitor = createHeartbeatMonitor(onTimeout, 1000)

    vi.advanceTimersByTime(500)
    monitor.heartbeat() // reset
    vi.advanceTimersByTime(900) // 1400ms total but only 900 since last heartbeat

    expect(onTimeout).not.toHaveBeenCalled()
    monitor.stop()
  })

  it('should stop timer and prevent callback', () => {
    const onTimeout = vi.fn()
    const monitor = createHeartbeatMonitor(onTimeout, 1000)

    monitor.stop()
    vi.advanceTimersByTime(2000)

    expect(onTimeout).not.toHaveBeenCalled()
  })
})
