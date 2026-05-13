import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import MessageBubble from '@components/Chat/MessageBubble'
import { Message } from '@/types/chat'
import { ThemeProvider, createTheme } from '@mui/material'

const theme = createTheme()

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <ThemeProvider theme={theme}>{children}</ThemeProvider>
)

const baseUserMessage: Message = {
  id: '1',
  session_id: 's1',
  role: 'user',
  content: 'Hello world',
  tool_calls: null,
  tool_results: null,
  created_at: '2026-04-30T10:00:00Z',
  parent_message_id: null,
  metadata: null,
  intent: null,
  intent_confidence: null,
  processing_status: 'completed',
  error_message: null,
}

const baseAssistantMessage: Message = {
  ...baseUserMessage,
  id: '2',
  role: 'assistant',
  content: 'I am an AI assistant',
  processing_status: 'completed',
}

describe('MessageBubble', () => {
  it('should render user message content', () => {
    render(<MessageBubble message={baseUserMessage} />, { wrapper })
    expect(screen.getByText('Hello world')).toBeInTheDocument()
  })

  it('should render assistant message content', () => {
    render(<MessageBubble message={baseAssistantMessage} />, { wrapper })
    expect(screen.getByText('I am an AI assistant')).toBeInTheDocument()
  })

  it('should show error state for failed messages', () => {
    const errorMsg: Message = {
      ...baseAssistantMessage,
      processing_status: 'failed',
      error_message: 'Something went wrong',
    }
    render(<MessageBubble message={errorMsg} />, { wrapper })
    expect(screen.getByText('Error')).toBeInTheDocument()
  })

  it('should show thinking indicator for processing messages', () => {
    const processingMsg: Message = {
      ...baseAssistantMessage,
      content: null,
      processing_status: 'processing',
    }
    render(<MessageBubble message={processingMsg} />, { wrapper })
    expect(screen.getByText('Thinking...')).toBeInTheDocument()
  })

  it('should expand tool calls on click', () => {
    const msgWithTools: Message = {
      ...baseAssistantMessage,
      tool_calls: [
        { id: 'tc1', type: 'function', function: { name: 'web_search', arguments: { query: 'test' } } },
      ],
    }
    render(<MessageBubble message={msgWithTools} />, { wrapper })

    const chip = screen.getByText('1 tool call')
    fireEvent.click(chip)
    expect(screen.getByText(/web_search/)).toBeInTheDocument()
  })

  it('should show tool result chips', () => {
    const msgWithResults: Message = {
      ...baseAssistantMessage,
      tool_results: [
        { tool_call_id: 'tc1', content: 'result', is_error: false, timestamp: '2026-04-30' },
        { tool_call_id: 'tc2', content: 'error', is_error: true, timestamp: '2026-04-30' },
      ],
    }
    render(<MessageBubble message={msgWithResults} />, { wrapper })
    expect(screen.getByText('Tool result')).toBeInTheDocument()
    expect(screen.getByText('Tool error')).toBeInTheDocument()
  })

  it('should call onRetry when retry button clicked', () => {
    const onRetry = vi.fn()
    const errorMsg: Message = {
      ...baseAssistantMessage,
      processing_status: 'failed',
      error_message: 'Error',
    }
    render(<MessageBubble message={errorMsg} onRetry={onRetry} />, { wrapper })

    const retryBtn = screen.getByRole('button', { name: /retry/i })
    fireEvent.click(retryBtn)
    expect(onRetry).toHaveBeenCalledWith('2')
  })

  it('should render content as plain text when not markdown', () => {
    const msg: Message = {
      ...baseUserMessage,
      content: '**bold** and _italic_',
    }
    render(<MessageBubble message={msg} />, { wrapper })
    expect(screen.getByText('**bold** and _italic_')).toBeInTheDocument()
  })

  it('should accept display name', () => {
    expect(MessageBubble.displayName).toBe('MessageBubble')
  })
})
