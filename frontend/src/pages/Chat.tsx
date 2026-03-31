import { useRef, useEffect, useState } from 'react'
import { Box, TextField, IconButton, Typography, Button } from '@mui/material'
import SendIcon from '@mui/icons-material/Send'
import AddIcon from '@mui/icons-material/Add'
import ChatBubble from '../components/chat/ChatBubble'
import StreamingIndicator from '../components/chat/StreamingIndicator'
import { useChatStore } from '../stores/chatStore'

export default function Chat() {
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
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      {/* Header */}
      <Box sx={{ p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid', borderColor: 'divider' }}>
        <Typography variant="h6" fontWeight={600}>Chat</Typography>
        <Button size="small" startIcon={<AddIcon />} onClick={clearChat}>New Chat</Button>
      </Box>

      {/* Messages */}
      <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
        {messages.length === 0 && !isStreaming && (
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
            <Box sx={{ textAlign: 'center', maxWidth: 480 }}>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Hello! I'm FinSight
              </Typography>
              <Typography color="text.secondary">
                Your financial intelligence assistant. Upload documents and ask me anything about your company's financial performance.
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

      {/* Input */}
      <Box sx={{ p: 2, borderTop: '1px solid', borderColor: 'divider', display: 'flex', gap: 1 }}>
        <TextField
          fullWidth
          multiline
          maxRows={3}
          placeholder="Ask about your financial data..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isStreaming}
          size="small"
        />
        <IconButton color="primary" onClick={handleSend} disabled={isStreaming || !input.trim()}>
          <SendIcon />
        </IconButton>
      </Box>
    </Box>
  )
}
