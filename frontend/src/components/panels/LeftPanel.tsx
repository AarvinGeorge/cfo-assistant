/**
 * LeftPanel.tsx
 *
 * Left panel of the 3-panel layout — the Sources panel where users manage
 * financial documents.
 *
 * Role in project:
 *   Document management UI. Reads from documentStore (document list, upload
 *   state) and renders the list of ingested files with type chips, status
 *   indicators, and hover-reveal delete buttons. Collapses to a 48px icon
 *   rail showing only the upload button.
 *
 * Main parts:
 *   - LeftPanel: main component with expanded/collapsed render paths.
 *   - renderUploadDialog(): MUI Dialog for file picker, doc_type dropdown,
 *     and fiscal_year field.
 *   - renderSnackbar(): success/error feedback after upload, rendered in
 *     both expanded and collapsed states to avoid silent failures.
 *   - Document list: maps documents to ListItem rows with type chips,
 *     status dot, and delete IconButton.
 */
import { useState } from 'react'
import {
  Box, Typography, TextField, IconButton, Tooltip,
  List, ListItem, ListItemIcon, ListItemText, Chip,
  Dialog, DialogTitle, DialogContent, DialogActions,
  Button, Select, MenuItem, FormControl, InputLabel,
  LinearProgress, Alert, Snackbar, CircularProgress,
} from '@mui/material'
import ArticleIcon from '@mui/icons-material/Article'
import TableChartIcon from '@mui/icons-material/TableChart'
import AddIcon from '@mui/icons-material/Add'
import DeleteIcon from '@mui/icons-material/Delete'
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft'
import ChevronRightIcon from '@mui/icons-material/ChevronRight'
import FolderOpenIcon from '@mui/icons-material/FolderOpen'
import { useDocumentStore } from '../../stores/documentStore'
import { useSessionStore } from '../../stores/sessionStore'

const DOC_TYPES = [
  '10-K', '10-Q', 'Income Statement', 'Balance Sheet',
  'Cash Flow Statement', 'Budget', 'Board Report', 'General',
]

export default function LeftPanel() {
  const { documents, loading, uploading, uploadDocument, deleteDocument } = useDocumentStore()
  const { leftPanelOpen, toggleLeftPanel } = useSessionStore()

  const [search, setSearch] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [docType, setDocType] = useState('General')
  const [fiscalYear, setFiscalYear] = useState('')
  const [uploadError, setUploadError] = useState('')
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' as 'success' | 'error' })

  const filtered = documents.filter((d) =>
    d.doc_name.toLowerCase().includes(search.toLowerCase())
  )

  const handleUpload = async () => {
    if (!file) return
    setUploadError('')
    try {
      await uploadDocument(file, docType, fiscalYear)
      setDialogOpen(false)
      setFile(null)
      setDocType('General')
      setFiscalYear('')
      setSnackbar({ open: true, message: 'Document uploaded and indexed successfully', severity: 'success' })
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Upload failed'
      setUploadError(msg)
    }
  }

  const handleDelete = async (docId: string) => {
    try {
      await deleteDocument(docId)
      setSnackbar({ open: true, message: 'Document deleted', severity: 'success' })
    } catch {
      setSnackbar({ open: true, message: 'Delete failed', severity: 'error' })
    }
    setDeleteConfirm(null)
  }

  const getDocIcon = (docType: string) =>
    docType.includes('Statement') || docType === 'Budget' || docType === '10-K' || docType === '10-Q'
      ? <TableChartIcon fontSize="small" />
      : <ArticleIcon fontSize="small" />

  // ── Collapsed rail ─────────────────────────────────────────
  if (!leftPanelOpen) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', height: '100%', py: 1 }}>
        {/* Logo */}
        <Box
          sx={{
            width: 32, height: 32, borderRadius: 2, bgcolor: 'primary.main',
            display: 'flex', alignItems: 'center', justifyContent: 'center', mb: 2, mt: 1,
          }}
        >
          <Typography sx={{ color: 'white', fontWeight: 700, fontSize: 16, lineHeight: 1 }}>F</Typography>
        </Box>

        {/* Nav icons */}
        <Tooltip title="Sources" placement="right">
          <IconButton size="small" sx={{ mb: 1, color: 'primary.main' }}>
            <FolderOpenIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title="Upload document" placement="right">
          <IconButton size="small" onClick={() => setDialogOpen(true)} sx={{ mb: 1 }}>
            <AddIcon fontSize="small" />
          </IconButton>
        </Tooltip>

        <Box sx={{ flex: 1 }} />

        {/* Expand button */}
        <Tooltip title="Expand panel" placement="right">
          <IconButton size="small" onClick={toggleLeftPanel} sx={{ mb: 1 }}>
            <ChevronRightIcon fontSize="small" />
          </IconButton>
        </Tooltip>

        {/* Dialogs and feedback shared between states */}
        {renderUploadDialog()}
        {renderSnackbar()}
      </Box>
    )
  }

  // ── Expanded panel ─────────────────────────────────────────
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header */}
      <Box
        sx={{
          display: 'flex', alignItems: 'center', px: 2, height: 56,
          borderBottom: '1px solid', borderColor: 'divider', flexShrink: 0,
        }}
      >
        {/* Logo */}
        <Box
          sx={{
            width: 28, height: 28, borderRadius: 1.5, bgcolor: 'primary.main',
            display: 'flex', alignItems: 'center', justifyContent: 'center', mr: 1.5,
          }}
        >
          <Typography sx={{ color: 'white', fontWeight: 700, fontSize: 14, lineHeight: 1 }}>F</Typography>
        </Box>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="body2" fontWeight={600} noWrap>FinSight</Typography>
          <Typography variant="caption" color="text.secondary" sx={{ lineHeight: 1 }}>CFO Assistant</Typography>
        </Box>
        <Tooltip title="Collapse panel">
          <IconButton size="small" onClick={toggleLeftPanel}>
            <ChevronLeftIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Search */}
      <Box sx={{ px: 1.5, py: 1.5, flexShrink: 0 }}>
        <TextField
          placeholder="Search documents..."
          size="small"
          fullWidth
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          sx={{
            '& .MuiOutlinedInput-root': {
              bgcolor: 'action.hover',
              '& fieldset': { borderColor: 'transparent' },
              '&:hover fieldset': { borderColor: 'divider' },
            },
          }}
        />
      </Box>

      {/* Section label */}
      <Typography
        variant="caption"
        sx={{ px: 2, pb: 0.5, color: 'text.secondary', fontWeight: 600, letterSpacing: '0.08em', flexShrink: 0 }}
      >
        SOURCES
      </Typography>

      {/* Document list */}
      <Box sx={{ flex: 1, overflowY: 'auto', px: 1 }}>
        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress size={24} />
          </Box>
        )}

        {!loading && filtered.length === 0 && (
          <Box sx={{ textAlign: 'center', py: 4, px: 2 }}>
            <FolderOpenIcon sx={{ fontSize: 32, color: 'text.disabled', mb: 1 }} />
            <Typography variant="body2" color="text.secondary">
              {search ? 'No documents match your search' : 'No documents yet. Click Upload to get started.'}
            </Typography>
          </Box>
        )}

        <List disablePadding>
          {filtered.map((doc) => (
            <ListItem
              key={doc.doc_id}
              disablePadding
              secondaryAction={
                <IconButton
                  edge="end"
                  size="small"
                  color="error"
                  onClick={() => setDeleteConfirm(doc.doc_id)}
                  sx={{ opacity: 0, '.MuiListItem-root:hover &': { opacity: 1 }, transition: 'opacity 0.15s' }}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              }
              sx={{
                mb: 0.5,
                borderRadius: 2,
                '&:hover': { bgcolor: 'action.hover' },
                '& .MuiListItemSecondaryAction-root': { right: 4 },
              }}
            >
              <Box
                sx={{
                  display: 'flex', alignItems: 'flex-start', gap: 1,
                  py: 1, pl: 1.5, pr: 4, width: '100%', cursor: 'default',
                }}
              >
                <ListItemIcon sx={{ minWidth: 0, mt: 0.25, color: 'text.secondary' }}>
                  {getDocIcon(doc.doc_type)}
                </ListItemIcon>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <ListItemText
                    primary={
                      <Typography variant="body2" fontWeight={500} noWrap sx={{ fontSize: 12 }}>
                        {doc.doc_name}
                      </Typography>
                    }
                    secondary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.25 }}>
                        <Chip
                          label={doc.doc_type}
                          size="small"
                          sx={{ height: 16, fontSize: 9, '& .MuiChip-label': { px: 0.75 } }}
                        />
                        <Box
                          sx={{
                            width: 6, height: 6, borderRadius: '50%',
                            bgcolor: doc.status === 'indexed' ? 'secondary.main' : 'warning.main',
                            ml: 'auto', flexShrink: 0,
                          }}
                        />
                      </Box>
                    }
                    disableTypography
                  />
                </Box>
              </Box>
            </ListItem>
          ))}
        </List>
      </Box>

      {/* Upload button */}
      <Box sx={{ p: 1.5, flexShrink: 0, borderTop: '1px solid', borderColor: 'divider' }}>
        <Button
          variant="contained"
          fullWidth
          startIcon={<AddIcon />}
          onClick={() => setDialogOpen(true)}
          sx={{ borderRadius: 2, textTransform: 'none' }}
        >
          Upload Document
        </Button>
      </Box>

      {renderUploadDialog()}
      {renderDeleteDialog()}
      {renderSnackbar()}
    </Box>
  )

  function renderUploadDialog() {
    return (
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Upload Document</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '16px !important' }}>
          <Button variant="outlined" component="label">
            {file ? file.name : 'Choose File'}
            <input
              type="file" hidden accept=".pdf,.csv,.txt,.html"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
          </Button>
          <FormControl fullWidth size="small">
            <InputLabel>Document Type</InputLabel>
            <Select value={docType} label="Document Type" onChange={(e) => setDocType(e.target.value)}>
              {DOC_TYPES.map((t) => <MenuItem key={t} value={t}>{t}</MenuItem>)}
            </Select>
          </FormControl>
          <TextField
            label="Fiscal Year" size="small"
            value={fiscalYear} onChange={(e) => setFiscalYear(e.target.value)}
            placeholder="e.g. 2024"
          />
          {uploading && <LinearProgress />}
          {uploadError && <Alert severity="error">{uploadError}</Alert>}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleUpload} disabled={!file || uploading}>Upload</Button>
        </DialogActions>
      </Dialog>
    )
  }

  function renderDeleteDialog() {
    return (
      <Dialog open={!!deleteConfirm} onClose={() => setDeleteConfirm(null)}>
        <DialogTitle>Delete Document?</DialogTitle>
        <DialogContent>
          This will remove the document and all its indexed vectors. This cannot be undone.
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirm(null)}>Cancel</Button>
          <Button
            color="error" variant="contained"
            onClick={() => deleteConfirm && handleDelete(deleteConfirm)}
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    )
  }

  function renderSnackbar() {
    return (
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar((s) => ({ ...s, open: false }))}
      >
        <Alert severity={snackbar.severity} variant="filled">{snackbar.message}</Alert>
      </Snackbar>
    )
  }
}
