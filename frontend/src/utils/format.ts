/**
 * 格式化工具函数
 */

import { format, formatDistanceToNow, formatRelative, isValid, parseISO } from 'date-fns'
import { zhCN, enUS } from 'date-fns/locale'

/**
 * 格式化时间戳为友好的显示字符串
 */
export function formatTimestamp(
  timestamp: string | Date | number,
  pattern: 'relative' | 'short' | 'full' | 'time' | 'date' = 'relative'
): string {
  const date = typeof timestamp === 'string' ? parseISO(timestamp) : new Date(timestamp)

  if (!isValid(date)) {
    return 'Invalid date'
  }

  switch (pattern) {
    case 'relative':
      return formatDistanceToNow(date, { addSuffix: true })
    case 'short':
      return format(date, 'MM/dd HH:mm')
    case 'full':
      return format(date, 'yyyy-MM-dd HH:mm:ss')
    case 'time':
      return format(date, 'HH:mm')
    case 'date':
      return format(date, 'yyyy-MM-dd')
    default:
      return format(date, 'yyyy-MM-dd HH:mm:ss')
  }
}

/**
 * 格式化消息时间显示
 */
export function formatMessageTime(timestamp: string): string {
  const date = parseISO(timestamp)
  if (!isValid(date)) return ''

  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`

  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`

  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 7) return `${diffDays}d ago`

  return format(date, 'MM/dd/yyyy')
}

/**
 * 截断文本并添加省略号
 */
export function truncateText(
  text: string,
  maxLength: number = 100,
  suffix: string = '...'
): string {
  if (!text || text.length <= maxLength) return text
  return text.substring(0, maxLength - suffix.length) + suffix
}

/**
 * 格式化字节大小
 */
export function formatBytes(bytes: number, decimals: number = 1): string {
  if (bytes === 0) return '0 B'

  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(decimals))} ${sizes[i]}`
}

/**
 * 格式化持续时间（毫秒）
 */
export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`

  const minutes = Math.floor(ms / 60000)
  const seconds = ((ms % 60000) / 1000).toFixed(0)
  return `${minutes}m ${seconds}s`
}

/**
 * 格式化数字（千分位）
 */
export function formatNumber(num: number, decimals: number = 0): string {
  return num.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

/**
 * 生成随机颜色
 */
export function randomColor(saturation: number = 70, lightness: number = 50): string {
  const hue = Math.floor(Math.random() * 360)
  return `hsl(${hue}, ${saturation}%, ${lightness}%)`
}

/**
 * 从字符串生成稳定的颜色
 */
export function stringToColor(str: string): string {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash)
  }
  const h = hash % 360
  return `hsl(${h}, 55%, 50%)`
}

/**
 * 格式化会话标题
 */
export function formatSessionTitle(title: string | null | undefined, sessionId: string): string {
  if (title && title.trim()) return title.trim()
  return `Session ${sessionId.slice(0, 8)}`
}

/**
 * 获取状态标签颜色
 */
export function getStatusColor(
  status: string
): 'default' | 'primary' | 'success' | 'warning' | 'error' | 'info' {
  const colorMap: Record<string, 'default' | 'primary' | 'success' | 'warning' | 'error' | 'info'> = {
    active: 'success',
    idle: 'success',
    busy: 'warning',
    processing: 'info',
    pending: 'warning',
    completed: 'success',
    failed: 'error',
    error: 'error',
    offline: 'default',
    archived: 'default',
    paused: 'warning',
  }
  return colorMap[status.toLowerCase()] || 'default'
}

/**
 * 提取文本第一行
 */
export function firstLine(text: string, maxLength: number = 80): string {
  const line = text.split('\n')[0]
  return truncateText(line, maxLength)
}

/**
 * 安全的JSON解析
 */
export function safeJsonParse<T = any>(json: string, fallback: T): T {
  try {
    return JSON.parse(json) as T
  } catch {
    return fallback
  }
}
