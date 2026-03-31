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
