/**
 * BackendUnreachableModal.tsx
 *
 * Blocking modal dialog shown when the FastAPI backend is not reachable
 * (ERR_CONNECTION_REFUSED / Network Error). Design matches Figma Variant D
 * on the "Phase 6 — Banner Variants" page of file L9k0ZL0p6CGWBfuUOt31ec.
 *
 * Role in project:
 *   Frontend UX layer. Reads `backendUnreachable` from connectionStore.
 *   Mounted once at the root of App.tsx so it can cover any panel. The
 *   Retry button fires a /health probe; on success, axiosClient's response
 *   interceptor clears the flag and the modal dismisses automatically.
 *
 * Main parts:
 *   - BackendUnreachableModal: functional component reading the Zustand flag
 *     and rendering an MUI Dialog with Retry + dismiss actions.
 *   - handleRetry: axios GET /health that, on success, implicitly clears the
 *     store flag via the response interceptor; on failure keeps the modal
 *     open with visual feedback.
 */
import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  Typography,
  Button,
  IconButton,
  Box,
  CircularProgress,
} from '@mui/material'
import CloseIcon from '@mui/icons-material/Close'
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline'
import { useConnectionStore } from '../../stores/connectionStore'
import axiosClient from '../../api/axiosClient'

export default function BackendUnreachableModal() {
  const backendUnreachable = useConnectionStore((s) => s.backendUnreachable)
  const setBackendUnreachable = useConnectionStore((s) => s.setBackendUnreachable)
  const [retrying, setRetrying] = useState(false)

  const handleRetry = async () => {
    setRetrying(true)
    try {
      // The response interceptor will clear backendUnreachable on success.
      await axiosClient.get('/health')
    } catch {
      // Interceptor already left the flag set — modal stays open.
    } finally {
      setRetrying(false)
    }
  }

  const handleDismiss = () => {
    // Optimistic dismiss — user may want to keep working even if backend
    // is down (e.g. to read historical content). Flag re-sets on the next
    // failed request.
    setBackendUnreachable(false)
  }

  return (
    <Dialog
      open={backendUnreachable}
      onClose={handleDismiss}
      maxWidth={false}
      PaperProps={{
        sx: {
          width: 520,
          borderRadius: '16px',
          bgcolor: 'background.paper',   // #2C2C2E (surface)
          border: '1px solid',
          borderColor: 'divider',          // #3A3A3C (elevated)
          boxShadow: '0 16px 40px rgba(0, 0, 0, 0.5)',
        },
      }}
      BackdropProps={{ sx: { bgcolor: 'rgba(0, 0, 0, 0.6)' } }}
    >
      <DialogContent sx={{ p: 4, position: 'relative' }}>
        {/* Dismiss × — top-right corner */}
        <IconButton
          onClick={handleDismiss}
          aria-label="Dismiss"
          sx={{ position: 'absolute', top: 12, right: 12, color: 'text.secondary' }}
        >
          <CloseIcon fontSize="small" />
        </IconButton>

        {/* Title row: error icon + heading */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1.5 }}>
          <ErrorOutlineIcon sx={{ color: 'error.main', fontSize: 28 }} />
          <Typography variant="h6" sx={{ fontWeight: 600, color: 'text.primary' }}>
            Backend not reachable
          </Typography>
        </Box>

        {/* Body copy */}
        <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1.5, lineHeight: 1.5 }}>
          FinSight can't reach the FastAPI backend at <code>localhost:8000</code>. This usually
          means the <code>make start</code> process isn't running, or the backend crashed during
          startup.
        </Typography>
        <Typography variant="body2" sx={{ color: 'text.secondary', mb: 3, lineHeight: 1.5 }}>
          Check the terminal where you ran <code>make start</code> for errors, or run{' '}
          <code>make doctor</code> to diagnose.
        </Typography>

        {/* Action row: Retry button */}
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1.5 }}>
          <Button
            onClick={handleRetry}
            disabled={retrying}
            variant="contained"
            color="primary"
            sx={{ minWidth: 112, borderRadius: '10px', textTransform: 'none', fontWeight: 500 }}
            startIcon={retrying ? <CircularProgress size={16} color="inherit" /> : null}
          >
            {retrying ? 'Checking…' : 'Retry'}
          </Button>
        </Box>
      </DialogContent>
    </Dialog>
  )
}
