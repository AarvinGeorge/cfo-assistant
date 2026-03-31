import { Box, CircularProgress, Typography } from '@mui/material'

interface StreamingIndicatorProps {
  label: string
}

export default function StreamingIndicator({ label }: StreamingIndicatorProps) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2, pl: 1 }}>
      <CircularProgress size={18} thickness={5} color="primary" />
      <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
        {label}
      </Typography>
    </Box>
  )
}
