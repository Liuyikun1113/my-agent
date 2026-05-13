import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import { Message, ChatRequest } from '@/types/chat'
import apiClient from '@/services/api'
import sseService from '@/services/sseService'

interface ChatStore {
  // State
  messages: Record<string, Message[]> // sessionId -> messages
  streamingMessage: Message | null
  isStreaming: boolean
  isLoading: boolean
  error: string | null

  // Actions
  setMessages: (sessionId: string, messages: Message[]) => void
  addMessage: (sessionId: string, message: Message) => void
  updateMessage: (sessionId: string, messageId: string, updates: Partial<Message>) => void
  setStreamingMessage: (message: Message | null) => void
  setStreaming: (streaming: boolean) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void

  // API Actions
  sendMessage: (sessionId: string, content: string, stream?: boolean) => Promise<Message>
  fetchMessages: (sessionId: string, page?: number, pageSize?: number) => Promise<Message[]>
  clearMessages: (sessionId: string) => void

  // SSE Actions
  connectSSE: (sessionId: string) => void
  disconnectSSE: () => void

  // Derived state
  getMessages: (sessionId: string) => Message[]
  getLastMessage: (sessionId: string) => Message | null
}

const useChatStore = create<ChatStore>()(
  devtools(
    (set, get) => ({
      // Initial state
      messages: {},
      streamingMessage: null,
      isStreaming: false,
      isLoading: false,
      error: null,

      // Basic setters
      setMessages: (sessionId, messages) =>
        set((state) => ({
          messages: {
            ...state.messages,
            [sessionId]: messages,
          },
        })),

      addMessage: (sessionId, message) =>
        set((state) => {
          const sessionMessages = state.messages[sessionId] || []
          return {
            messages: {
              ...state.messages,
              [sessionId]: [...sessionMessages, message],
            },
          }
        }),

      updateMessage: (sessionId, messageId, updates) =>
        set((state) => {
          const sessionMessages = state.messages[sessionId]
          if (!sessionMessages) return state

          return {
            messages: {
              ...state.messages,
              [sessionId]: sessionMessages.map((msg) =>
                msg.id === messageId ? { ...msg, ...updates } : msg
              ),
            },
          }
        }),

      setStreamingMessage: (message) => set({ streamingMessage: message }),
      setStreaming: (streaming) => set({ isStreaming: streaming }),
      setLoading: (loading) => set({ isLoading: loading }),
      setError: (error) => set({ error }),

      // API Actions
      sendMessage: async (sessionId, content) => {
        set({ isLoading: true, error: null })

        try {
          // Create placeholder for assistant response (will be updated via SSE)
          const assistantMessage: Message = {
            id: `streaming-${Date.now()}`,
            session_id: sessionId,
            role: 'assistant',
            content: '',
            tool_calls: null,
            tool_results: null,
            created_at: new Date().toISOString(),
            parent_message_id: null,
            metadata: null,
            intent: null,
            intent_confidence: null,
            processing_status: 'processing',
            error_message: null,
          }

          set({ streamingMessage: assistantMessage, isStreaming: true })
          get().addMessage(sessionId, assistantMessage)

          // Send via API — backend triggers process_user_message → SSE push
          await apiClient.sendMessage(sessionId, content)

          return assistantMessage
        } catch (error: any) {
          set({ error: error.message || 'Failed to send message' })
          console.error('Failed to send message:', error)
          throw error
        } finally {
          set({ isLoading: false })
        }
      },

      fetchMessages: async (sessionId, page = 1, pageSize = 50) => {
        set({ isLoading: true, error: null })
        try {
          const response = await apiClient.getMessages(sessionId, page, pageSize)
          const messages = response.items || response
          get().setMessages(sessionId, messages)
          return messages
        } catch (error: any) {
          set({ error: error.message || 'Failed to fetch messages' })
          console.error('Failed to fetch messages:', error)
          throw error
        } finally {
          set({ isLoading: false })
        }
      },

      clearMessages: (sessionId) => {
        set((state) => ({
          messages: {
            ...state.messages,
            [sessionId]: [],
          },
        }))
      },

      // SSE Actions
      connectSSE: (sessionId) => {
        sseService.connect(sessionId)

        // Setup SSE event handlers
        sseService.onMessage((event) => {
          if (event.event === 'CHAT_MESSAGE' || event.event === 'message') {
            const data = event.data
            const msg = data.message || data
            const state = get()

            // Replace streaming placeholder if present
            if (state.streamingMessage && state.streamingMessage.id.startsWith('streaming-')) {
              get().updateMessage(sessionId, state.streamingMessage.id, {
                id: msg.id,
                content: msg.content,
                processing_status: 'completed',
              })
              set({ streamingMessage: null, isStreaming: false })
            } else {
              get().addMessage(sessionId, msg)
            }
          } else if (event.event === 'CHAT_DELTA') {
            const data = event.data
            const state = get()
            if (state.streamingMessage && data.delta) {
              get().updateMessage(sessionId, state.streamingMessage.id, {
                content: (state.streamingMessage.content || '') + data.delta,
              })
            }
          } else if (event.event === 'INTENT_UPDATE') {
            console.log('Intent update:', event.data)
          }
        })

        sseService.onError((error) => {
          console.error('SSE error:', error)
          set({ error: 'SSE connection error' })
        })

        sseService.onOpen(() => {
          console.log('SSE connected')
        })

        sseService.onClose(() => {
          console.log('SSE disconnected')
        })
      },

      disconnectSSE: () => {
        sseService.disconnect()
      },

      // Derived state
      getMessages: (sessionId) => {
        return get().messages[sessionId] || []
      },

      getLastMessage: (sessionId) => {
        const messages = get().messages[sessionId] || []
        return messages.length > 0 ? messages[messages.length - 1] : null
      },
    }),
    {
      name: 'ChatStore',
    }
  )
)

export default useChatStore