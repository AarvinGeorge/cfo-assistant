/**
 * CreateWorkspaceModal.tsx
 *
 * MUI Dialog that creates a new workspace.
 *
 * Role in project:
 *   Rendered by WorkspaceSwitcher when the user clicks "+ New Workspace".
 *   Calls workspaceStore.createWorkspace on submit; invokes onCreated
 *   callback so the parent can auto-switch to the new workspace.
 *
 * Main parts:
 *   - Props: open, onClose, onCreated (Workspace => void)
 *   - Local form state: name, description, submitting flag, error string
 *   - Validation: name required, max 80 chars; description max 500
 */
import { useState } from 'react'
import {
  Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions,
  TextField, Button, Alert,
} from '@mui/material'
import { useWorkspaceStore } from '../../stores/workspaceStore'
import { Workspace } from '../../types'

interface Props {
  open: boolean
  onClose: () => void
  onCreated: (workspace: Workspace) => void
}

export function CreateWorkspaceModal({ open, onClose, onCreated }: Props) {
  const createWorkspace = useWorkspaceStore((s) => s.createWorkspace)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const trimmedName = name.trim()
  const nameInvalid = trimmedName.length === 0 || trimmedName.length > 80
  const descInvalid = description.length > 500
  const canSubmit = !nameInvalid && !descInvalid && !submitting

  const handleClose = () => {
    if (submitting) return
    setName('')
    setDescription('')
    setError(null)
    onClose()
  }

  const handleSubmit = async () => {
    if (!canSubmit) return
    setSubmitting(true)
    setError(null)
    try {
      const newWorkspace = await createWorkspace(trimmedName, description.trim() || undefined)
      onCreated(newWorkspace)
      setName('')
      setDescription('')
      onClose()
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? err?.message ?? 'Failed to create workspace')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="xs" fullWidth>
      <DialogTitle>Create new workspace</DialogTitle>
      <DialogContent>
        <DialogContentText sx={{ mb: 2, fontSize: 12 }}>
          A workspace is a company or deal context. Documents and conversations are scoped to it.
        </DialogContentText>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <TextField
          autoFocus
          fullWidth
          required
          label="Name"
          placeholder="e.g. Acme Corp"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && canSubmit) handleSubmit() }}
          inputProps={{ maxLength: 80 }}
          helperText={nameInvalid && trimmedName.length > 80 ? 'Max 80 characters' : ' '}
          error={trimmedName.length > 80}
          sx={{ mb: 2 }}
        />
        <TextField
          fullWidth
          label="Description (optional)"
          placeholder="e.g. FY26 audit + M&A review"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          multiline
          rows={2}
          inputProps={{ maxLength: 500 }}
          helperText={descInvalid ? 'Max 500 characters' : ' '}
          error={descInvalid}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={submitting}>Cancel</Button>
        <Button onClick={handleSubmit} disabled={!canSubmit} variant="contained">
          {submitting ? 'Creating…' : 'Create workspace'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
