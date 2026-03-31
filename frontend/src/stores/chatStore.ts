import { create } from 'zustand'
import { ChatMessage } from '../types'
import { useSessionStore } from './sessionStore'

interface ChatState {
  messages: ChatMessage[]
  isStreaming: boolean
  streamingLabel: string
  sendMessage: (content: string) => Promise<void>
  clearChat: () => void
}

export const useChatStore = create<ChatState>((set, _get) => ({
  messages: [],
  isStreaming: false,
  streamingLabel: '',

  sendMessage: async (content: string) => {
    const sessionId = useSessionStore.getState().sessionId

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      timestamp: Date.now(),
    }
    set((s) => ({ messages: [...s.messages, userMsg], isStreaming: true, streamingLabel: 'Thinking...' }))

    try {
      const res = await fetch('http://localhost:8000/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: content, session_id: sessionId }),
      })

      if (!res.ok || !res.body) throw new Error('Stream failed')

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let fullResponse = ''
      let citations: string[] = []

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))

            switch (event.type) {
              case 'session':
                useSessionStore.getState().setSessionId(event.session_id)
                break
              case 'intent':
                set({ streamingLabel: `Classified as: ${event.intent}` })
                break
              case 'retrieval':
                set({ streamingLabel: `Retrieved ${event.chunk_count} relevant chunks...` })
                break
              case 'model_output':
                set({ streamingLabel: 'Running financial model...' })
                break
              case 'response':
                fullResponse = event.content
                break
              case 'done':
                citations = event.citations || []
                break
              case 'error':
                throw new Error(event.message)
            }
          } catch (e) {
            if (e instanceof SyntaxError) continue
            throw e
          }
        }
      }

      const assistantMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: fullResponse,
        citations,
        timestamp: Date.now(),
      }
      set((s) => ({ messages: [...s.messages, assistantMsg], isStreaming: false, streamingLabel: '' }))

    } catch (err) {
      const errorMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'error',
        content: err instanceof Error ? err.message : 'An error occurred',
        timestamp: Date.now(),
      }
      set((s) => ({ messages: [...s.messages, errorMsg], isStreaming: false, streamingLabel: '' }))
    }
  },

  clearChat: () => {
    useSessionStore.getState().setSessionId(crypto.randomUUID())
    set({ messages: [], isStreaming: false, streamingLabel: '' })
  },
}))
