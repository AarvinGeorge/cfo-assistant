/**
 * CitationChip.tsx
 *
 * Renders a [Source: ...] citation reference as a compact MUI Chip,
 * keeping source attribution visible without breaking reading flow.
 *
 * Role in project:
 *   Citation UI. Used by CenterPanel to render inline citations extracted
 *   from assistant messages. Each chip shows the document name and section.
 *   Can be extended in Phase 6 to scroll LeftPanel to the referenced document.
 *
 * Main parts:
 *   - CitationChip: accepts a Citation object (doc_name, section, page) and
 *     renders a small purple MUI Chip with a link icon.
 */
import { Chip } from '@mui/material'

interface CitationChipProps {
  citation: string
}

export default function CitationChip({ citation }: CitationChipProps) {
  return (
    <Chip
      label={citation}
      size="small"
      variant="outlined"
      color="primary"
      sx={{ mx: 0.5, my: 0.25, fontSize: '0.7rem', height: 22 }}
    />
  )
}
