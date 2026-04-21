/**
 * App.tsx
 *
 * Root layout component — renders the 3-panel shell that contains the
 * entire FinSight UI, plus a top-level BackendUnreachableModal that blocks
 * interaction when the backend is down.
 *
 * Role in project:
 *   Single authoritative layout. There is no React Router — App.tsx IS the
 *   application. It owns the panel width calculations, collapse transitions,
 *   the single fetchDocuments() call that populates LeftPanel on mount, and
 *   the workspace-change effect that refetches documents and clears chat when
 *   the active workspace changes.
 *
 * Main parts:
 *   - LEFT_W / RIGHT_W / COLLAPSED_W: module-level constants (280 / 340 / 48px)
 *     used for panel sizing and CSS transitions.
 *   - App: reads leftPanelOpen and rightPanelOpen from sessionStore, renders
 *     three flex children (LeftPanel, CenterPanel, RightPanel) with width
 *     transitions driven by panel state, plus BackendUnreachableModal.
 *   - fetchWorkspaces() on mount: populates the WorkspaceSwitcher dropdown.
 *   - workspace-change effect: refetches documents and clears chat on workspaceId
 *     change so the user sees a fresh context for each workspace.
 */
import { useEffect } from 'react'
import { Box } from '@mui/material'
import { useSessionStore } from './stores/sessionStore'
import { useDocumentStore } from './stores/documentStore'
import { useChatStore } from './stores/chatStore'
import { useWorkspaceStore } from './stores/workspaceStore'
import LeftPanel from './components/panels/LeftPanel'
import CenterPanel from './components/panels/CenterPanel'
import RightPanel from './components/panels/RightPanel'
import BackendUnreachableModal from './components/common/BackendUnreachableModal'

const LEFT_W = 280
const RIGHT_W = 340
const COLLAPSED_W = 48

export default function App() {
  const { leftPanelOpen, rightPanelOpen } = useSessionStore()
  const workspaceId = useSessionStore((s) => s.workspaceId)
  const fetchDocuments = useDocumentStore((s) => s.fetchDocuments)
  const clearChat = useChatStore((s) => s.clearChat)
  const fetchWorkspaces = useWorkspaceStore((s) => s.fetchWorkspaces)

  // Fetch workspaces once on mount to populate the WorkspaceSwitcher dropdown
  useEffect(() => {
    fetchWorkspaces()
  }, [fetchWorkspaces])

  // Single authoritative fetch — prevents LeftPanel + RightPanel both firing on mount.
  // Also re-fetches and clears chat when the active workspace changes so the user
  // sees a fresh context for the new workspace.
  useEffect(() => {
    fetchDocuments()
    clearChat()
  }, [workspaceId, fetchDocuments, clearChat])

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

      {/* Blocking modal shown when backend is unreachable (ERR_NETWORK) */}
      <BackendUnreachableModal />
    </Box>
  )
}
