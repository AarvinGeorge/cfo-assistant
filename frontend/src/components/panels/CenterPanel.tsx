/**
 * CenterPanel.tsx
 *
 * Centre panel of the 3-panel layout — the Chat panel where users
 * converse with FinSight.
 *
 * Role in project:
 *   Primary interaction surface. Reads from chatStore (messages, streaming
 *   state) and sessionStore (session ID). Renders the conversation history
 *   using ChatBubble components, shows a StreamingIndicator while a response
 *   is in-flight, and provides the message input bar with send button.
 *
 * Main parts:
 *   - CenterPanel: manages auto-scroll to latest message, input state, and
 *     submit handler that calls chatStore.sendMessage().
 *   - Message list: maps chatStore.messages to ChatBubble and CitationChip rows.
 *   - Input bar: MUI TextField with conditional send button styling — active
 *     only when input is non-empty and not streaming.
 *   - StreamingIndicator: shown below the last message while isStreaming is true.
 */
import { useRef, useEffect, useState } from 'react'
import { Box, TextField, IconButton, Typography, Tooltip } from '@mui/material'
import SendIcon from '@mui/icons-material/Send'
import AddCommentIcon from '@mui/icons-material/AddComment'
import ChatBubble from '../chat/ChatBubble'
import StreamingIndicator from '../chat/StreamingIndicator'
import { useChatStore } from '../../stores/chatStore'

export default function CenterPanel() {
  const { messages, isStreaming, streamingLabel, sendMessage, clearChat } = useChatStore()
  const [input, setInput] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isStreaming])

  const handleSend = () => {
    const trimmed = input.trim()
    if (!trimmed || isStreaming) return
    setInput('')
    sendMessage(trimmed)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header */}
      <Box
        sx={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          px: 3, height: 56, borderBottom: '1px solid', borderColor: 'divider',
          flexShrink: 0,
        }}
      >
        <Typography variant="body1" fontWeight={600}>Chat</Typography>
        <Tooltip title="New chat">
          <IconButton size="small" onClick={clearChat}>
            <AddCommentIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Messages */}
      <Box sx={{ flex: 1, overflowY: 'auto', px: 3, py: 2 }}>
        {messages.length === 0 && !isStreaming && (
          <Box
            sx={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              height: '100%',
            }}
          >
            <Box sx={{ textAlign: 'center', maxWidth: 440 }}>
              <Box
                sx={{
                  width: 48, height: 48, borderRadius: 3, bgcolor: 'primary.main',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  mx: 'auto', mb: 2,
                }}
              >
                <Typography sx={{ color: 'white', fontWeight: 700, fontSize: 20, lineHeight: 1 }}>F</Typography>
              </Box>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Hello, I&apos;m FinSight
              </Typography>
              <Typography color="text.secondary" variant="body2">
                Your financial intelligence assistant. Upload documents in the Sources panel and ask me anything about your company&apos;s financial performance, forecasts, or scenarios.
              </Typography>
            </Box>
          </Box>
        )}

        {messages.map((msg) => (
          <ChatBubble key={msg.id} message={msg} />
        ))}

        {isStreaming && <StreamingIndicator label={streamingLabel} />}

        <div ref={scrollRef} />
      </Box>

      {/* Input bar */}
      <Box
        sx={{
          px: 2, py: 1.5,
          borderTop: '1px solid', borderColor: 'divider',
          display: 'flex', alignItems: 'flex-end', gap: 1,
          flexShrink: 0, bgcolor: 'background.default',
        }}
      >
        <TextField
          fullWidth
          multiline
          maxRows={4}
          placeholder="Ask about your financial documents..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isStreaming}
          size="small"
          sx={{
            '& .MuiOutlinedInput-root': {
              bgcolor: 'background.paper',
              borderRadius: 2,
            },
          }}
        />
        <IconButton
          onClick={handleSend}
          disabled={isStreaming || !input.trim()}
          sx={{
            bgcolor: input.trim() && !isStreaming ? 'primary.main' : 'transparent',
            color: input.trim() && !isStreaming ? 'white' : 'action.disabled',
            borderRadius: 2,
            width: 38, height: 38,
            flexShrink: 0,
            '&:hover': {
              bgcolor: input.trim() && !isStreaming ? 'primary.dark' : 'transparent',
            },
            '&.Mui-disabled': {
              bgcolor: 'transparent',
              color: 'action.disabled',
            },
          }}
        >
          <SendIcon fontSize="small" />
        </IconButton>
      </Box>
    </Box>
  )
}
