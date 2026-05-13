/**
 * 重连策略工具
 * 为SSE和WebSocket提供指数退避重连逻辑
 */

export interface ReconnectionConfig {
  initialDelay: number
  maxDelay: number
  maxAttempts: number
  backoffMultiplier: number
  jitterEnabled: boolean
  jitterFactor: number
  resetAfterSuccess: boolean
  onAttempt?: (attempt: number, delay: number) => void
  onMaxAttemptsReached?: () => void
}

export type ReconnectionState = 'disconnected' | 'connecting' | 'connected' | 'waiting';

export class ReconnectionManager {
  private config: Required<ReconnectionConfig>
  private attempts: number = 0
  private state: ReconnectionState = 'disconnected'
  private timer: ReturnType<typeof setTimeout> | null = null
  private onReconnect: () => Promise<boolean> | boolean

  constructor(
    onReconnect: () => Promise<boolean> | boolean,
    config: Partial<ReconnectionConfig> = {}
  ) {
    this.onReconnect = onReconnect
    this.config = {
      initialDelay: config.initialDelay ?? 1000,
      maxDelay: config.maxDelay ?? 30000,
      maxAttempts: config.maxAttempts ?? 10,
      backoffMultiplier: config.backoffMultiplier ?? 2,
      jitterEnabled: config.jitterEnabled ?? true,
      jitterFactor: config.jitterFactor ?? 0.2,
      resetAfterSuccess: config.resetAfterSuccess ?? true,
      onAttempt: config.onAttempt ?? (() => {}),
      onMaxAttemptsReached: config.onMaxAttemptsReached ?? (() => {}),
    }
  }

  /**
   * Start reconnection attempts
   */
  start(): void {
    if (this.state === 'connecting' || this.state === 'waiting') {
      return
    }
    this.attempts = 0
    this.scheduleNext()
  }

  /**
   * Stop all reconnection attempts
   */
  stop(): void {
    if (this.timer) {
      clearTimeout(this.timer)
      this.timer = null
    }
    this.state = 'disconnected'
    this.attempts = 0
  }

  /**
   * Mark connection as successful
   */
  onSuccess(): void {
    this.state = 'connected'
    if (this.config.resetAfterSuccess) {
      this.attempts = 0
    }
  }

  /**
   * Trigger immediate reconnection (e.g., on unexpected disconnect)
   */
  onDisconnect(): void {
    this.state = 'disconnected'
    this.scheduleNext()
  }

  /**
   * Schedule the next reconnection attempt
   */
  private scheduleNext(): void {
    if (this.attempts >= this.config.maxAttempts) {
      this.state = 'disconnected'
      this.config.onMaxAttemptsReached()
      return
    }

    const delay = this.calculateDelay()
    this.state = 'waiting'
    this.config.onAttempt(this.attempts + 1, delay)

    this.timer = setTimeout(async () => {
      this.state = 'connecting'
      try {
        const success = await this.onReconnect()
        if (success) {
          this.onSuccess()
        } else {
          this.attempts++
          this.scheduleNext()
        }
      } catch {
        this.attempts++
        this.scheduleNext()
      }
    }, delay)
  }

  /**
   * Calculate backoff delay with optional jitter
   */
  private calculateDelay(): number {
    const baseDelay = this.config.initialDelay * Math.pow(
      this.config.backoffMultiplier,
      this.attempts
    )
    const cappedDelay = Math.min(baseDelay, this.config.maxDelay)

    if (this.config.jitterEnabled) {
      const jitterRange = cappedDelay * this.config.jitterFactor
      const jitter = (Math.random() * 2 - 1) * jitterRange
      return Math.round(Math.max(0, cappedDelay + jitter))
    }

    return Math.round(cappedDelay)
  }

  getState(): ReconnectionState {
    return this.state
  }

  getAttempts(): number {
    return this.attempts
  }

  getConfig(): Required<ReconnectionConfig> {
    return { ...this.config }
  }
}

/**
 * 预定义的重连策略
 */
export const ReconnectionStrategies = {
  /** 快速重连：短间隔，适用于开发环境 */
  fast: (): Partial<ReconnectionConfig> => ({
    initialDelay: 500,
    maxDelay: 5000,
    maxAttempts: 20,
    backoffMultiplier: 1.5,
  }),

  /** 标准重连：平衡性能和体验 */
  standard: (): Partial<ReconnectionConfig> => ({
    initialDelay: 1000,
    maxDelay: 30000,
    maxAttempts: 10,
    backoffMultiplier: 2,
  }),

  /** 保守重连：长间隔，减少服务器压力 */
  conservative: (): Partial<ReconnectionConfig> => ({
    initialDelay: 3000,
    maxDelay: 60000,
    maxAttempts: 5,
    backoffMultiplier: 2.5,
  }),

  /** 持久重连：一直尝试，适用于关键连接 */
  persistent: (): Partial<ReconnectionConfig> => ({
    initialDelay: 2000,
    maxDelay: 30000,
    maxAttempts: Infinity,
    backoffMultiplier: 2,
  }),
}

/**
 * 计算指数退避延迟（独立函数，不依赖ReconnectionManager）
 */
export function calculateBackoffDelay(
  attempt: number,
  baseDelay: number = 1000,
  maxDelay: number = 30000,
  multiplier: number = 2,
  jitter: boolean = true
): number {
  const exponentialDelay = baseDelay * Math.pow(multiplier, attempt - 1)
  const cappedDelay = Math.min(exponentialDelay, maxDelay)

  if (jitter) {
    const jitterRange = cappedDelay * 0.2
    const jitterValue = (Math.random() * 2 - 1) * jitterRange
    return Math.round(Math.max(0, cappedDelay + jitterValue))
  }

  return Math.round(cappedDelay)
}
