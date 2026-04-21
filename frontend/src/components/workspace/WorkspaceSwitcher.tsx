/**
 * WorkspaceSwitcher.tsx
 *
 * Dropdown button + menu rendered at the top of LeftPanel. Shows the
 * active workspace name with a chevron; click to open a menu listing
 * all workspaces plus a "+ New Workspace" action.
 *
 * Role in project:
 *   Primary navigation for the multi-workspace UX. Reads from
 *   workspaceStore (list) + sessionStore (active id). Writes to
 *   sessionStore.setWorkspaceId on selection. Renders
 *   CreateWorkspaceModal conditionally.
 *
 * Main parts:
 *   - Button with current workspace name + chevron
 *   - MUI Menu with workspace items (active shows accent dot)
 *   - Divider + "+ New Workspace" action at the bottom
 *   - Renders CreateWorkspaceModal; auto-switches to new workspace on create
 */
import { useState, useRef, MouseEvent } from 'react'
import {
  Button, Menu, MenuItem, Divider, ListItemIcon, ListItemText, Box, Typography,
} from '@mui/material'
import CircleIcon from '@mui/icons-material/FiberManualRecord'
import AddIcon from '@mui/icons-material/Add'
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown'
import { useSessionStore } from '../../stores/sessionStore'
import { useWorkspaceStore } from '../../stores/workspaceStore'
import { CreateWorkspaceModal } from './CreateWorkspaceModal'
import { Workspace } from '../../types'

export function WorkspaceSwitcher() {
  const workspaces = useWorkspaceStore((s) => s.workspaces)
  const loading = useWorkspaceStore((s) => s.loading)
  const workspaceId = useSessionStore((s) => s.workspaceId)
  const setWorkspaceId = useSessionStore((s) => s.setWorkspaceId)

  const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const buttonRef = useRef<HTMLButtonElement>(null)

  const activeWorkspace = workspaces.find((w) => w.id === workspaceId)
  const activeLabel = activeWorkspace?.name ?? (loading ? 'Loading…' : 'Default Workspace')

  const openMenu = (e: MouseEvent<HTMLButtonElement>) => setMenuAnchor(e.currentTarget)
  const closeMenu = () => setMenuAnchor(null)

  const handleSelect = (id: string) => {
    setWorkspaceId(id)
    closeMenu()
  }

  const handleOpenCreate = () => {
    closeMenu()
    setModalOpen(true)
  }

  const handleCreated = (newWorkspace: Workspace) => {
    // Auto-switch to the new workspace (D4 from spec)
    setWorkspaceId(newWorkspace.id)
  }

  return (
    <>
      <Button
        ref={buttonRef}
        onClick={openMenu}
        fullWidth
        variant="outlined"
        endIcon={<KeyboardArrowDownIcon />}
        sx={{
          justifyContent: 'space-between',
          textTransform: 'none',
          bgcolor: 'background.paper',
          borderColor: Boolean(menuAnchor) ? 'primary.main' : 'divider',
          color: 'text.primary',
          py: 1,
          px: 1.5,
          '&:hover': { borderColor: 'primary.main' },
        }}
      >
        <Typography noWrap sx={{ fontWeight: 500 }}>{activeLabel}</Typography>
      </Button>

      <Menu
        anchorEl={menuAnchor}
        open={Boolean(menuAnchor)}
        onClose={closeMenu}
        PaperProps={{
          sx: { minWidth: buttonRef.current?.offsetWidth ?? 240, mt: 0.5 },
        }}
      >
        {workspaces.map((w) => {
          const isActive = w.id === workspaceId
          return (
            <MenuItem key={w.id} onClick={() => handleSelect(w.id)} selected={isActive}>
              <ListItemIcon sx={{ minWidth: 24 }}>
                {isActive
                  ? <CircleIcon sx={{ fontSize: 8, color: 'primary.main' }} />
                  : <Box sx={{ width: 8 }} />}
              </ListItemIcon>
              <ListItemText primary={w.name} />
            </MenuItem>
          )
        })}
        <Divider />
        <MenuItem onClick={handleOpenCreate} sx={{ color: 'primary.main' }}>
          <ListItemIcon sx={{ minWidth: 24 }}>
            <AddIcon fontSize="small" sx={{ color: 'primary.main' }} />
          </ListItemIcon>
          <ListItemText primary="New Workspace" primaryTypographyProps={{ fontWeight: 500 }} />
        </MenuItem>
      </Menu>

      <CreateWorkspaceModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreated={handleCreated}
      />
    </>
  )
}
