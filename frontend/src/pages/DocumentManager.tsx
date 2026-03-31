import { useEffect, useState } from 'react'
import {
  Box, Typography, Button, TextField, Dialog, DialogTitle, DialogContent,
  DialogActions, Select, MenuItem, FormControl, InputLabel, LinearProgress,
  IconButton, Chip, Snackbar, Alert,
} from '@mui/material'
import { DataGrid, GridColDef } from '@mui/x-data-grid'
import AddIcon from '@mui/icons-material/Add'
import DeleteIcon from '@mui/icons-material/Delete'
import { useDocumentStore } from '../stores/documentStore'

const DOC_TYPES = [
  '10-K', '10-Q', 'Income Statement', 'Balance Sheet',
  'Cash Flow Statement', 'Budget', 'Board Report', 'General',
]

export default function DocumentManager() {
  const { documents, loading, uploading, fetchDocuments, uploadDocument, deleteDocument } = useDocumentStore()
  const [search, setSearch] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [docType, setDocType] = useState('General')
  const [fiscalYear, setFiscalYear] = useState('')
  const [uploadError, setUploadError] = useState('')
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' as 'success' | 'error' })
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)

  useEffect(() => { fetchDocuments() }, [fetchDocuments])

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

  const columns: GridColDef[] = [
    { field: 'doc_name', headerName: 'Name', flex: 2 },
    { field: 'doc_type', headerName: 'Type', flex: 1 },
    { field: 'fiscal_year', headerName: 'Year', flex: 0.7 },
    { field: 'chunk_count', headerName: 'Chunks', flex: 0.5, type: 'number' },
    {
      field: 'status', headerName: 'Status', flex: 0.7,
      renderCell: (params) => (
        <Chip
          label={params.value}
          size="small"
          color={params.value === 'indexed' ? 'success' : 'warning'}
          variant="outlined"
        />
      ),
    },
    {
      field: 'actions', headerName: '', flex: 0.4, sortable: false,
      renderCell: (params) => (
        <IconButton size="small" color="error" onClick={() => setDeleteConfirm(params.row.doc_id)}>
          <DeleteIcon fontSize="small" />
        </IconButton>
      ),
    },
  ]

  return (
    <Box sx={{ p: 3, height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5" fontWeight={600}>Documents</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setDialogOpen(true)}>
          Upload
        </Button>
      </Box>

      {/* Search */}
      <TextField
        placeholder="Search documents..."
        size="small"
        fullWidth
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        sx={{ mb: 2 }}
      />

      {/* Table */}
      <Box sx={{ flex: 1, minHeight: 0 }}>
        <DataGrid
          rows={filtered}
          columns={columns}
          getRowId={(row) => row.doc_id}
          loading={loading}
          disableRowSelectionOnClick
          pageSizeOptions={[10, 25]}
          initialState={{ pagination: { paginationModel: { pageSize: 10 } } }}
          sx={{ border: 'none', '& .MuiDataGrid-cell': { borderColor: 'divider' } }}
          localeText={{ noRowsLabel: 'No documents uploaded yet. Click + Upload to get started.' }}
        />
      </Box>

      {/* Upload Dialog */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Upload Document</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '16px !important' }}>
          <Button variant="outlined" component="label">
            {file ? file.name : 'Choose File'}
            <input type="file" hidden accept=".pdf,.csv,.txt,.html" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          </Button>
          <FormControl fullWidth size="small">
            <InputLabel>Document Type</InputLabel>
            <Select value={docType} label="Document Type" onChange={(e) => setDocType(e.target.value)}>
              {DOC_TYPES.map((t) => <MenuItem key={t} value={t}>{t}</MenuItem>)}
            </Select>
          </FormControl>
          <TextField label="Fiscal Year" size="small" value={fiscalYear} onChange={(e) => setFiscalYear(e.target.value)} placeholder="e.g. 2024" />
          {uploading && <LinearProgress />}
          {uploadError && <Alert severity="error">{uploadError}</Alert>}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleUpload} disabled={!file || uploading}>Upload</Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirmation */}
      <Dialog open={!!deleteConfirm} onClose={() => setDeleteConfirm(null)}>
        <DialogTitle>Delete Document?</DialogTitle>
        <DialogContent>This will remove the document and all its indexed vectors. This cannot be undone.</DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirm(null)}>Cancel</Button>
          <Button color="error" variant="contained" onClick={() => deleteConfirm && handleDelete(deleteConfirm)}>Delete</Button>
        </DialogActions>
      </Dialog>

      {/* Snackbar */}
      <Snackbar open={snackbar.open} autoHideDuration={4000} onClose={() => setSnackbar((s) => ({ ...s, open: false }))}>
        <Alert severity={snackbar.severity} variant="filled">{snackbar.message}</Alert>
      </Snackbar>
    </Box>
  )
}
