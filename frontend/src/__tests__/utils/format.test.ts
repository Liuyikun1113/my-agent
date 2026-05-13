import { describe, it, expect } from 'vitest'
import {
  formatTimestamp,
  formatMessageTime,
  truncateText,
  formatBytes,
  formatDuration,
  formatNumber,
  stringToColor,
  safeJsonParse,
  getStatusColor,
} from '@utils/format'

describe('formatTimestamp', () => {
  it('should format date string', () => {
    const result = formatTimestamp('2026-04-30T10:30:00Z')
    expect(result).toBeTruthy()
    expect(typeof result).toBe('string')
  })

  it('should format with custom pattern', () => {
    const result = formatTimestamp('2026-04-30T10:30:00Z', 'yyyy-MM-dd')
    expect(result).toBe('2026-04-30')
  })

  it('should return empty for invalid date', () => {
    expect(formatTimestamp('invalid')).toBe('')
    expect(formatTimestamp('')).toBe('')
  })
})

describe('formatMessageTime', () => {
  it('should return time for today', () => {
    const now = new Date()
    const result = formatMessageTime(now.toISOString())
    expect(result).toBeTruthy()
  })

  it('should return "Yesterday" for yesterday', () => {
    const yesterday = new Date(Date.now() - 86400000)
    const result = formatMessageTime(yesterday.toISOString())
    expect(result).toContain('Yesterday')
  })
})

describe('truncateText', () => {
  it('should return short text unchanged', () => {
    expect(truncateText('hello', 10)).toBe('hello')
  })

  it('should truncate long text', () => {
    const result = truncateText('hello world, this is a long text', 15)
    expect(result.length).toBeLessThanOrEqual(18) // text + "..."
  })

  it('should return empty string for empty input', () => {
    expect(truncateText('', 10)).toBe('')
  })
})

describe('formatBytes', () => {
  it('should format 0 bytes', () => {
    expect(formatBytes(0)).toBe('0 B')
  })

  it('should format bytes', () => {
    expect(formatBytes(500)).toBe('500 B')
  })

  it('should format KB', () => {
    const result = formatBytes(1024)
    expect(result).toContain('KB')
  })

  it('should format MB', () => {
    const result = formatBytes(1048576)
    expect(result).toContain('MB')
  })
})

describe('formatDuration', () => {
  it('should format seconds', () => {
    expect(formatDuration(5)).toContain('s')
  })

  it('should format minutes', () => {
    const result = formatDuration(120)
    expect(result).toContain('min')
  })

  it('should format hours', () => {
    const result = formatDuration(3600)
    expect(result).toContain('h')
  })
})

describe('formatNumber', () => {
  it('should format small numbers', () => {
    expect(formatNumber(42)).toBe('42')
  })

  it('should format large numbers', () => {
    const result = formatNumber(1234567)
    expect(result).toContain(',')
  })
})

describe('stringToColor', () => {
  it('should return consistent color for same input', () => {
    const c1 = stringToColor('test')
    const c2 = stringToColor('test')
    expect(c1).toBe(c2)
  })

  it('should return different colors for different input', () => {
    const c1 = stringToColor('test1')
    const c2 = stringToColor('test2')
    expect(c1).not.toBe(c2)
  })

  it('should return valid hex color', () => {
    const color = stringToColor('hello')
    expect(color).toMatch(/^#[0-9a-fA-F]{3,6}$/)
  })
})

describe('safeJsonParse', () => {
  it('should parse valid JSON', () => {
    expect(safeJsonParse('{"a":1}')).toEqual({ a: 1 })
  })

  it('should return default for invalid JSON', () => {
    expect(safeJsonParse('invalid', null)).toBeNull()
  })

  it('should return default for empty string', () => {
    expect(safeJsonParse('', [])).toEqual([])
  })
})

describe('getStatusColor', () => {
  it('should return success for active', () => {
    expect(getStatusColor('active')).toBeTruthy()
  })

  it('should return warning for paused', () => {
    expect(getStatusColor('paused')).toBeTruthy()
  })

  it('should return error for failed', () => {
    expect(getStatusColor('failed')).toBeTruthy()
  })

  it('should return default for unknown status', () => {
    expect(getStatusColor('unknown')).toBeTruthy()
  })
})
