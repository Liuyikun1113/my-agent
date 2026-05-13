export type MessageRole = 'user' | 'assistant' | 'system' | 'tool'

export interface ToolCall {
  id: string
  type: 'function'
  function: {
    name: string
    arguments: Record<string, any>
  }
}

export interface ToolResult {
  tool_call_id: string
  content: string
  is_error: boolean
  timestamp: string
}

export interface Message {
  id: string
  session_id: string
  role: MessageRole
  content: string | null
  tool_calls: ToolCall[] | null
  tool_results: ToolResult[] | null
  created_at: string
  parent_message_id: string | null
  metadata: Record<string, any> | null
  intent: string | null
  intent_confidence: number | null
  processing_status: 'pending' | 'processing' | 'completed' | 'failed'
  error_message: string | null
}

export interface ChatRequest {
  session_id: string
  message: string
  stream?: boolean
}

export interface ChatResponse {
  message: Message
  is_streaming?: boolean
  stream_token?: string
}

export interface SSEEvent {
  event: 'message' | 'heartbeat' | 'error' | 'status'
  data: any
  retry?: number
}