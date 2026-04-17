/**
 * ChatBubble.tsx
 *
 * Renders a single chat message as a styled bubble — user messages aligned
 * right, assistant messages aligned left with full markdown support.
 *
 * Role in project:
 *   Presentational component. Used by CenterPanel to render each message in
 *   the conversation history. Assistant messages are rendered with
 *   react-markdown and remark-gfm to support tables, lists, and bold text
 *   from Claude financial analysis responses.
 *
 * Main parts:
 *   - ChatBubble: accepts a ChatMessage prop and renders the appropriate
 *     bubble layout, background colour, and alignment.
 *   - Markdown renderer: configured with remark-gfm for GitHub Flavored
 *     Markdown, with MUI Typography overrides for table and list styling.
 */
import { Box } from '@mui/material'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import CitationChip from './CitationChip'
import { ChatMessage } from '../../types'

interface ChatBubbleProps {
  message: ChatMessage
}

function parseCitations(content: string): { text: string; citations: string[] } {
  const citations: string[] = []
  const text = content.replace(/\[Source: ([^\]]+)\]/g, (_, citation) => {
    citations.push(citation)
    return `%%CITE_${citations.length - 1}%%`
  })
  return { text, citations }
}

export default function ChatBubble({ message }: ChatBubbleProps) {
  const isUser = message.role === 'user'
  const isError = message.role === 'error'

  if (isUser) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
        <Box sx={{
          maxWidth: '70%', px: 2, py: 1.5, borderRadius: 3,
          bgcolor: 'primary.main', color: 'white',
        }}>
          {message.content}
        </Box>
      </Box>
    )
  }

  const { text, citations } = parseCitations(message.content)
  const parts = text.split(/(%%CITE_\d+%%)/g)

  return (
    <Box sx={{ display: 'flex', justifyContent: 'flex-start', mb: 2 }}>
      <Box sx={{
        maxWidth: '80%', px: 2, py: 1.5, borderRadius: 3,
        bgcolor: isError ? 'error.dark' : 'background.paper',
        border: '1px solid',
        borderColor: isError ? 'error.main' : 'divider',
        '& table': { borderCollapse: 'collapse', width: '100%', my: 1 },
        '& th, & td': { border: '1px solid', borderColor: 'divider', px: 1, py: 0.5, fontSize: '0.85rem' },
        '& th': { bgcolor: 'action.hover', fontWeight: 600 },
        '& p': { my: 0.5 },
        '& ul, & ol': { pl: 2.5, my: 0.5 },
        '& code': { bgcolor: 'action.hover', px: 0.5, borderRadius: 0.5, fontSize: '0.85rem' },
      }}>
        {parts.map((part, i) => {
          const citeMatch = part.match(/%%CITE_(\d+)%%/)
          if (citeMatch) {
            const idx = parseInt(citeMatch[1])
            return <CitationChip key={i} citation={citations[idx]} />
          }
          return (
            <ReactMarkdown key={i} remarkPlugins={[remarkGfm]}>
              {part}
            </ReactMarkdown>
          )
        })}
      </Box>
    </Box>
  )
}
