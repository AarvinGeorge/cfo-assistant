import { useEffect } from 'react'
import { Box } from '@mui/material'
import { useSessionStore } from './stores/sessionStore'
import { useDocumentStore } from './stores/documentStore'
import LeftPanel from './components/panels/LeftPanel'
import CenterPanel from './components/panels/CenterPanel'
import RightPanel from './components/panels/RightPanel'

const LEFT_W = 280
const RIGHT_W = 340
const COLLAPSED_W = 48

export default function App() {
  const { leftPanelOpen, rightPanelOpen } = useSessionStore()
  const { fetchDocuments } = useDocumentStore()

  // Single authoritative fetch — prevents LeftPanel + RightPanel both firing on mount
  useEffect(() => { fetchDocuments() }, [fetchDocuments])

  return (
    <Box
      sx={{
        display: 'flex',
        height: '100vh',
        width: '100vw',
        overflow: 'hidden',
        bgcolor: 'background.default',
      }}
    >
      {/* Left panel — Sources */}
      <Box
        sx={{
          width: leftPanelOpen ? LEFT_W : COLLAPSED_W,
          minWidth: leftPanelOpen ? LEFT_W : COLLAPSED_W,
          transition: 'width 0.25s ease, min-width 0.25s ease',
          overflow: 'hidden',
          borderRight: '1px solid',
          borderColor: 'divider',
          display: 'flex',
          flexDirection: 'column',
          bgcolor: 'background.paper',
          flexShrink: 0,
        }}
      >
        <LeftPanel />
      </Box>

      {/* Center panel — Chat */}
      <Box sx={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <CenterPanel />
      </Box>

      {/* Right panel — Studio */}
      <Box
        sx={{
          width: rightPanelOpen ? RIGHT_W : COLLAPSED_W,
          minWidth: rightPanelOpen ? RIGHT_W : COLLAPSED_W,
          transition: 'width 0.25s ease, min-width 0.25s ease',
          overflow: 'hidden',
          borderLeft: '1px solid',
          borderColor: 'divider',
          display: 'flex',
          flexDirection: 'column',
          bgcolor: 'background.paper',
          flexShrink: 0,
        }}
      >
        <RightPanel />
      </Box>
    </Box>
  )
}
