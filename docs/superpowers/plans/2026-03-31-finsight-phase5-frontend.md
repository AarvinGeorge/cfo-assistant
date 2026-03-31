# FinSight Phase 5: Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working React frontend MVP with 3 pages (Dashboard, Chat, Documents) that connects to the existing FastAPI backend at localhost:8000.

**Architecture:** Vite + React 18 + TypeScript SPA. MUI v6 for all components (no other CSS). Zustand for state. Axios for REST, native fetch for SSE. Page-first build order: shared shell → Documents → Chat → Dashboard. Components extracted into a shared library as they emerge.

**Tech Stack:** React 18, TypeScript, Vite, MUI v6, Zustand, Axios, react-markdown, remark-gfm, react-router-dom v6

**Reference:** `CLAUDE.md` for conventions. `docs/superpowers/specs/2026-03-31-finsight-phase5-frontend-design.md` for full spec.

---

## File Map

```
frontend/
├── index.html                        # Vite entry, Inter font
├── vite.config.ts                    # Vite config with React plugin, proxy to backend
├── tsconfig.node.json                # Vite/node tsconfig
├── src/
│   ├── main.tsx                      # ReactDOM, ThemeProvider, Router
│   ├── App.tsx                       # Layout: Sidebar + Outlet
│   ├── vite-env.d.ts                 # Vite type declarations
│   ├── types/
│   │   └── index.ts                  # Shared interfaces
│   ├── theme/
│   │   └── muiTheme.ts              # Dark + light themes
│   ├── api/
│   │   └── axiosClient.ts           # Axios instance
│   ├── stores/
│   │   ├── sessionStore.ts          # Theme, session_id, sidebar
│   │   ├── documentStore.ts         # Documents CRUD
│   │   ├── chatStore.ts             # Chat messages, SSE streaming
│   │   └── dashboardStore.ts        # KPI values
│   ├── components/
│   │   ├── layout/
│   │   │   └── Sidebar.tsx          # Navigation sidebar
│   │   └── chat/
│   │       ├── ChatBubble.tsx       # Message bubble with markdown
│   │       ├── CitationChip.tsx     # Inline source citation
│   │       └── StreamingIndicator.tsx # Thinking/loading state
│   └── pages/
│       ├── Dashboard.tsx
│       ├── Chat.tsx
│       └── DocumentManager.tsx
└── package.json                      # MODIFY: add react-markdown, remark-gfm
```

---

### Task 1: Vite Config + Entry Point + Theme + Types

**Files:**
- Create: `frontend/index.html`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/src/vite-env.d.ts`
- Create: `frontend/src/types/index.ts`
- Create: `frontend/src/theme/muiTheme.ts`
- Create: `frontend/src/api/axiosClient.ts`
- Create: `frontend/src/stores/sessionStore.ts`
- Modify: `frontend/package.json` (add react-markdown, remark-gfm)

- [ ] **Step 1: Add dependencies**

```bash
cd frontend
npm install react-markdown remark-gfm
```

- [ ] **Step 2: Create index.html**

`frontend/index.html`:
```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet" />
    <title>FinSight CFO Assistant</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 3: Create vite.config.ts**

`frontend/vite.config.ts`:
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
```

- [ ] **Step 4: Create tsconfig.node.json**

`frontend/tsconfig.node.json`:
```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 5: Create vite-env.d.ts**

`frontend/src/vite-env.d.ts`:
```typescript
/// <reference types="vite/client" />
```

- [ ] **Step 6: Create types/index.ts**

`frontend/src/types/index.ts`:
```typescript
export interface Document {
  doc_id: string
  doc_name: string
  doc_type: string
  fiscal_year: string
  chunk_count: number
  status: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'error'
  content: string
  intent?: string
  citations?: string[]
  timestamp: number
}

export interface KPIValue {
  value: string
  rawValue: number
  change?: string
  favorable?: boolean
}

export interface HealthStatus {
  status: string
  redis: boolean
  pinecone: boolean
  anthropic_key: boolean
  gemini_key: boolean
}
```

- [ ] **Step 7: Create muiTheme.ts**

`frontend/src/theme/muiTheme.ts`:
```typescript
import { createTheme } from '@mui/material/styles'

const sharedTypography = {
  fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
}

const sharedShape = {
  borderRadius: 12,
}

export const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: '#7c4dff' },
    secondary: { main: '#00e676' },
    error: { main: '#ff5252' },
    background: {
      default: '#1a1a2e',
      paper: '#1e1e2f',
    },
  },
  typography: sharedTypography,
  shape: sharedShape,
  components: {
    MuiCard: {
      styleOverrides: {
        root: { backgroundImage: 'none' },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: { textTransform: 'none', fontWeight: 600 },
      },
    },
  },
})

export const lightTheme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: '#7c4dff' },
    secondary: { main: '#00c853' },
    error: { main: '#ff5252' },
    background: {
      default: '#f5f5f5',
      paper: '#ffffff',
    },
  },
  typography: sharedTypography,
  shape: sharedShape,
  components: {
    MuiButton: {
      styleOverrides: {
        root: { textTransform: 'none', fontWeight: 600 },
      },
    },
  },
})
```

- [ ] **Step 8: Create axiosClient.ts**

`frontend/src/api/axiosClient.ts`:
```typescript
import axios from 'axios'

const axiosClient = axios.create({
  baseURL: 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' },
})

axiosClient.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message)
    return Promise.reject(error)
  }
)

export default axiosClient
```

- [ ] **Step 9: Create sessionStore.ts**

`frontend/src/stores/sessionStore.ts`:
```typescript
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface SessionState {
  themeMode: 'dark' | 'light'
  sessionId: string
  sidebarCollapsed: boolean
  toggleTheme: () => void
  setSessionId: (id: string) => void
  toggleSidebar: () => void
}

export const useSessionStore = create<SessionState>()(
  persist(
    (set) => ({
      themeMode: 'dark',
      sessionId: crypto.randomUUID(),
      sidebarCollapsed: false,
      toggleTheme: () =>
        set((s) => ({ themeMode: s.themeMode === 'dark' ? 'light' : 'dark' })),
      setSessionId: (id: string) => set({ sessionId: id }),
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
    }),
    { name: 'finsight-session' }
  )
)
```

- [ ] **Step 10: Verify build compiles**

```bash
cd frontend
npx tsc --noEmit
npx vite build
```

Expected: no TypeScript errors, build succeeds.

- [ ] **Step 11: Commit**

```bash
git add frontend/index.html frontend/vite.config.ts frontend/tsconfig.node.json frontend/src/
git commit -m "feat(frontend): Vite config, MUI theme, types, Axios client, session store"
```

---

### Task 2: Layout Shell (App + Sidebar + Routing)

**Files:**
- Create: `frontend/src/components/layout/Sidebar.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/pages/Dashboard.tsx` (placeholder)
- Create: `frontend/src/pages/Chat.tsx` (placeholder)
- Create: `frontend/src/pages/DocumentManager.tsx` (placeholder)

- [ ] **Step 1: Create Sidebar.tsx**

`frontend/src/components/layout/Sidebar.tsx`:
```typescript
import { Box, Drawer, List, ListItemButton, ListItemIcon, ListItemText, IconButton, Tooltip } from '@mui/material'
import DashboardIcon from '@mui/icons-material/Dashboard'
import ChatIcon from '@mui/icons-material/Chat'
import DescriptionIcon from '@mui/icons-material/Description'
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft'
import ChevronRightIcon from '@mui/icons-material/ChevronRight'
import DarkModeIcon from '@mui/icons-material/DarkMode'
import LightModeIcon from '@mui/icons-material/LightMode'
import { useLocation, useNavigate } from 'react-router-dom'
import { useSessionStore } from '../../stores/sessionStore'

const EXPANDED_WIDTH = 240
const COLLAPSED_WIDTH = 64

const navItems = [
  { label: 'Dashboard', icon: <DashboardIcon />, path: '/dashboard' },
  { label: 'Chat', icon: <ChatIcon />, path: '/chat' },
  { label: 'Documents', icon: <DescriptionIcon />, path: '/documents' },
]

export default function Sidebar() {
  const location = useLocation()
  const navigate = useNavigate()
  const { sidebarCollapsed, toggleSidebar, themeMode, toggleTheme } = useSessionStore()

  const width = sidebarCollapsed ? COLLAPSED_WIDTH : EXPANDED_WIDTH

  return (
    <Drawer
      variant="permanent"
      sx={{
        width,
        flexShrink: 0,
        '& .MuiDrawer-paper': {
          width,
          boxSizing: 'border-box',
          borderRight: '1px solid',
          borderColor: 'divider',
          transition: 'width 0.2s ease',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        },
      }}
    >
      {/* Logo */}
      <Box sx={{ p: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
        <Box
          sx={{
            width: 32,
            height: 32,
            borderRadius: 1.5,
            bgcolor: 'primary.main',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'white',
            fontWeight: 700,
            fontSize: 14,
            flexShrink: 0,
          }}
        >
          F
        </Box>
        {!sidebarCollapsed && (
          <Box sx={{ fontWeight: 700, fontSize: 16, whiteSpace: 'nowrap' }}>FinSight</Box>
        )}
      </Box>

      {/* Navigation */}
      <List sx={{ flex: 1, px: 1 }}>
        {navItems.map((item) => {
          const active = location.pathname === item.path
          return (
            <Tooltip key={item.path} title={sidebarCollapsed ? item.label : ''} placement="right">
              <ListItemButton
                onClick={() => navigate(item.path)}
                sx={{
                  borderRadius: 2,
                  mb: 0.5,
                  bgcolor: active ? 'primary.main' : 'transparent',
                  color: active ? 'white' : 'text.secondary',
                  '&:hover': { bgcolor: active ? 'primary.main' : 'action.hover' },
                  minHeight: 44,
                  justifyContent: sidebarCollapsed ? 'center' : 'flex-start',
                  px: sidebarCollapsed ? 1 : 2,
                }}
              >
                <ListItemIcon
                  sx={{
                    color: 'inherit',
                    minWidth: sidebarCollapsed ? 0 : 36,
                    justifyContent: 'center',
                  }}
                >
                  {item.icon}
                </ListItemIcon>
                {!sidebarCollapsed && <ListItemText primary={item.label} />}
              </ListItemButton>
            </Tooltip>
          )
        })}
      </List>

      {/* Bottom controls */}
      <Box sx={{ p: 1, display: 'flex', flexDirection: 'column', gap: 0.5 }}>
        <Tooltip title={themeMode === 'dark' ? 'Light mode' : 'Dark mode'} placement="right">
          <IconButton onClick={toggleTheme} size="small" sx={{ alignSelf: sidebarCollapsed ? 'center' : 'flex-start' }}>
            {themeMode === 'dark' ? <LightModeIcon fontSize="small" /> : <DarkModeIcon fontSize="small" />}
          </IconButton>
        </Tooltip>
        <Tooltip title={sidebarCollapsed ? 'Expand' : 'Collapse'} placement="right">
          <IconButton onClick={toggleSidebar} size="small" sx={{ alignSelf: sidebarCollapsed ? 'center' : 'flex-start' }}>
            {sidebarCollapsed ? <ChevronRightIcon fontSize="small" /> : <ChevronLeftIcon fontSize="small" />}
          </IconButton>
        </Tooltip>
      </Box>
    </Drawer>
  )
}
```

- [ ] **Step 2: Create placeholder pages**

`frontend/src/pages/Dashboard.tsx`:
```typescript
import { Box, Typography } from '@mui/material'

export default function Dashboard() {
  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" fontWeight={600}>Dashboard</Typography>
      <Typography color="text.secondary" sx={{ mt: 1 }}>Coming soon...</Typography>
    </Box>
  )
}
```

`frontend/src/pages/Chat.tsx`:
```typescript
import { Box, Typography } from '@mui/material'

export default function Chat() {
  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" fontWeight={600}>Chat</Typography>
      <Typography color="text.secondary" sx={{ mt: 1 }}>Coming soon...</Typography>
    </Box>
  )
}
```

`frontend/src/pages/DocumentManager.tsx`:
```typescript
import { Box, Typography } from '@mui/material'

export default function DocumentManager() {
  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" fontWeight={600}>Documents</Typography>
      <Typography color="text.secondary" sx={{ mt: 1 }}>Coming soon...</Typography>
    </Box>
  )
}
```

- [ ] **Step 3: Create App.tsx**

`frontend/src/App.tsx`:
```typescript
import { Box } from '@mui/material'
import { Outlet } from 'react-router-dom'
import Sidebar from './components/layout/Sidebar'

export default function App() {
  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <Sidebar />
      <Box component="main" sx={{ flexGrow: 1, overflow: 'auto' }}>
        <Outlet />
      </Box>
    </Box>
  )
}
```

- [ ] **Step 4: Create main.tsx**

`frontend/src/main.tsx`:
```typescript
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ThemeProvider, CssBaseline } from '@mui/material'
import { useSessionStore } from './stores/sessionStore'
import { darkTheme, lightTheme } from './theme/muiTheme'
import App from './App'
import Dashboard from './pages/Dashboard'
import Chat from './pages/Chat'
import DocumentManager from './pages/DocumentManager'

function Root() {
  const themeMode = useSessionStore((s) => s.themeMode)
  const theme = themeMode === 'dark' ? darkTheme : lightTheme

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<App />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="chat" element={<Chat />} />
            <Route path="documents" element={<DocumentManager />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
)
```

- [ ] **Step 5: Verify dev server starts**

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`. Verify: dark background, purple sidebar with 3 nav items, "Dashboard" placeholder visible, navigation works between all 3 pages, theme toggle switches dark/light, sidebar collapses.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/
git commit -m "feat(frontend): layout shell — Sidebar, routing, placeholder pages"
```

---

### Task 3: Document Store + DocumentManager Page

**Files:**
- Create: `frontend/src/stores/documentStore.ts`
- Rewrite: `frontend/src/pages/DocumentManager.tsx`

- [ ] **Step 1: Create documentStore.ts**

`frontend/src/stores/documentStore.ts`:
```typescript
import { create } from 'zustand'
import axiosClient from '../api/axiosClient'
import { Document } from '../types'

interface DocumentState {
  documents: Document[]
  loading: boolean
  uploading: boolean
  fetchDocuments: () => Promise<void>
  uploadDocument: (file: File, docType: string, fiscalYear: string) => Promise<void>
  deleteDocument: (docId: string) => Promise<void>
}

export const useDocumentStore = create<DocumentState>((set, get) => ({
  documents: [],
  loading: false,
  uploading: false,

  fetchDocuments: async () => {
    set({ loading: true })
    try {
      const res = await axiosClient.get('/documents/')
      set({ documents: res.data, loading: false })
    } catch {
      set({ documents: [], loading: false })
    }
  },

  uploadDocument: async (file: File, docType: string, fiscalYear: string) => {
    set({ uploading: true })
    const formData = new FormData()
    formData.append('file', file)
    formData.append('doc_type', docType)
    formData.append('fiscal_year', fiscalYear)
    try {
      await axiosClient.post('/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      await get().fetchDocuments()
    } finally {
      set({ uploading: false })
    }
  },

  deleteDocument: async (docId: string) => {
    await axiosClient.delete(`/documents/${docId}`)
    await get().fetchDocuments()
  },
}))
```

- [ ] **Step 2: Rewrite DocumentManager.tsx**

`frontend/src/pages/DocumentManager.tsx`:
```typescript
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
```

- [ ] **Step 3: Verify**

```bash
cd frontend && npx tsc --noEmit && npm run dev
```

Open `http://localhost:5173/documents`. Verify: header with "Documents" + Upload button, empty DataGrid showing "No documents uploaded yet", Upload dialog opens on button click, theme toggle still works.

With backend running (`PYTHONPATH=. uvicorn backend.api.main:app --port 8000`): verify document list loads, upload works, delete works.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/stores/documentStore.ts frontend/src/pages/DocumentManager.tsx
git commit -m "feat(frontend): Documents page with upload, list, delete, DataGrid"
```

---

### Task 4: Chat Components (ChatBubble, CitationChip, StreamingIndicator)

**Files:**
- Create: `frontend/src/components/chat/ChatBubble.tsx`
- Create: `frontend/src/components/chat/CitationChip.tsx`
- Create: `frontend/src/components/chat/StreamingIndicator.tsx`

- [ ] **Step 1: Create CitationChip.tsx**

`frontend/src/components/chat/CitationChip.tsx`:
```typescript
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
```

- [ ] **Step 2: Create ChatBubble.tsx**

`frontend/src/components/chat/ChatBubble.tsx`:
```typescript
import { Box } from '@mui/material'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import CitationChip from './CitationChip'
import { ChatMessage } from '../../types'

interface ChatBubbleProps {
  message: ChatMessage
}

function parseCitations(content: string): { text: string; citations: string[] } {
  const citations: string[] = []
  const text = content.replace(/\[Source: ([^\]]+)\]/g, (_, citation) => {
    citations.push(citation)
    return `%%CITE_${citations.length - 1}%%`
  })
  return { text, citations }
}

export default function ChatBubble({ message }: ChatBubbleProps) {
  const isUser = message.role === 'user'
  const isError = message.role === 'error'

  if (isUser) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
        <Box sx={{
          maxWidth: '70%', px: 2, py: 1.5, borderRadius: 3,
          bgcolor: 'primary.main', color: 'white',
        }}>
          {message.content}
        </Box>
      </Box>
    )
  }

  const { text, citations } = parseCitations(message.content)

  // Split on citation placeholders and reconstruct with chips
  const parts = text.split(/(%%CITE_\d+%%)/g)

  return (
    <Box sx={{ display: 'flex', justifyContent: 'flex-start', mb: 2 }}>
      <Box sx={{
        maxWidth: '80%', px: 2, py: 1.5, borderRadius: 3,
        bgcolor: isError ? 'error.dark' : 'background.paper',
        border: '1px solid',
        borderColor: isError ? 'error.main' : 'divider',
        '& table': { borderCollapse: 'collapse', width: '100%', my: 1 },
        '& th, & td': { border: '1px solid', borderColor: 'divider', px: 1, py: 0.5, fontSize: '0.85rem' },
        '& th': { bgcolor: 'action.hover', fontWeight: 600 },
        '& p': { my: 0.5 },
        '& ul, & ol': { pl: 2.5, my: 0.5 },
        '& code': { bgcolor: 'action.hover', px: 0.5, borderRadius: 0.5, fontSize: '0.85rem' },
      }}>
        {parts.map((part, i) => {
          const citeMatch = part.match(/%%CITE_(\d+)%%/)
          if (citeMatch) {
            const idx = parseInt(citeMatch[1])
            return <CitationChip key={i} citation={citations[idx]} />
          }
          return (
            <ReactMarkdown key={i} remarkPlugins={[remarkGfm]}>
              {part}
            </ReactMarkdown>
          )
        })}
      </Box>
    </Box>
  )
}
```

- [ ] **Step 3: Create StreamingIndicator.tsx**

`frontend/src/components/chat/StreamingIndicator.tsx`:
```typescript
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
```

- [ ] **Step 4: Verify build**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/chat/
git commit -m "feat(frontend): chat components — ChatBubble, CitationChip, StreamingIndicator"
```

---

### Task 5: Chat Store + Chat Page

**Files:**
- Create: `frontend/src/stores/chatStore.ts`
- Rewrite: `frontend/src/pages/Chat.tsx`

- [ ] **Step 1: Create chatStore.ts**

`frontend/src/stores/chatStore.ts`:
```typescript
import { create } from 'zustand'
import { ChatMessage } from '../types'
import { useSessionStore } from './sessionStore'

interface ChatState {
  messages: ChatMessage[]
  isStreaming: boolean
  streamingLabel: string
  sendMessage: (content: string) => Promise<void>
  clearChat: () => void
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  isStreaming: false,
  streamingLabel: '',

  sendMessage: async (content: string) => {
    const sessionId = useSessionStore.getState().sessionId

    // Add user message
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      timestamp: Date.now(),
    }
    set((s) => ({ messages: [...s.messages, userMsg], isStreaming: true, streamingLabel: 'Thinking...' }))

    try {
      const res = await fetch('http://localhost:8000/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: content, session_id: sessionId }),
      })

      if (!res.ok || !res.body) throw new Error('Stream failed')

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let fullResponse = ''
      let citations: string[] = []

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))

            switch (event.type) {
              case 'session':
                useSessionStore.getState().setSessionId(event.session_id)
                break
              case 'intent':
                set({ streamingLabel: `Classified as: ${event.intent}` })
                break
              case 'retrieval':
                set({ streamingLabel: `Retrieved ${event.chunk_count} relevant chunks...` })
                break
              case 'model_output':
                set({ streamingLabel: 'Running financial model...' })
                break
              case 'response':
                fullResponse = event.content
                break
              case 'done':
                citations = event.citations || []
                break
              case 'error':
                throw new Error(event.message)
            }
          } catch (e) {
            if (e instanceof SyntaxError) continue
            throw e
          }
        }
      }

      const assistantMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: fullResponse,
        citations,
        timestamp: Date.now(),
      }
      set((s) => ({ messages: [...s.messages, assistantMsg], isStreaming: false, streamingLabel: '' }))

    } catch (err) {
      const errorMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'error',
        content: err instanceof Error ? err.message : 'An error occurred',
        timestamp: Date.now(),
      }
      set((s) => ({ messages: [...s.messages, errorMsg], isStreaming: false, streamingLabel: '' }))
    }
  },

  clearChat: () => {
    useSessionStore.getState().setSessionId(crypto.randomUUID())
    set({ messages: [], isStreaming: false, streamingLabel: '' })
  },
}))
```

- [ ] **Step 2: Rewrite Chat.tsx**

`frontend/src/pages/Chat.tsx`:
```typescript
import { useRef, useEffect, useState } from 'react'
import { Box, TextField, IconButton, Typography, Button } from '@mui/material'
import SendIcon from '@mui/icons-material/Send'
import AddIcon from '@mui/icons-material/Add'
import ChatBubble from '../components/chat/ChatBubble'
import StreamingIndicator from '../components/chat/StreamingIndicator'
import { useChatStore } from '../stores/chatStore'

export default function Chat() {
  const { messages, isStreaming, streamingLabel, sendMessage, clearChat } = useChatStore()
  const [input, setInput] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isStreaming])

  const handleSend = () => {
    const trimmed = input.trim()
    if (!trimmed || isStreaming) return
    setInput('')
    sendMessage(trimmed)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      {/* Header */}
      <Box sx={{ p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid', borderColor: 'divider' }}>
        <Typography variant="h6" fontWeight={600}>Chat</Typography>
        <Button size="small" startIcon={<AddIcon />} onClick={clearChat}>New Chat</Button>
      </Box>

      {/* Messages */}
      <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
        {messages.length === 0 && !isStreaming && (
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
            <Box sx={{ textAlign: 'center', maxWidth: 480 }}>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Hello! I'm FinSight
              </Typography>
              <Typography color="text.secondary">
                Your financial intelligence assistant. Upload documents and ask me anything about your company's financial performance.
              </Typography>
            </Box>
          </Box>
        )}
        {messages.map((msg) => (
          <ChatBubble key={msg.id} message={msg} />
        ))}
        {isStreaming && <StreamingIndicator label={streamingLabel} />}
        <div ref={scrollRef} />
      </Box>

      {/* Input */}
      <Box sx={{ p: 2, borderTop: '1px solid', borderColor: 'divider', display: 'flex', gap: 1 }}>
        <TextField
          fullWidth
          multiline
          maxRows={3}
          placeholder="Ask about your financial data..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isStreaming}
          size="small"
        />
        <IconButton color="primary" onClick={handleSend} disabled={isStreaming || !input.trim()}>
          <SendIcon />
        </IconButton>
      </Box>
    </Box>
  )
}
```

- [ ] **Step 3: Verify**

```bash
cd frontend && npx tsc --noEmit && npm run dev
```

Open `http://localhost:5173/chat`. Verify: welcome message centered, input bar at bottom, "New Chat" button in header. With backend running: type a message, see streaming indicator update, see response with citation chips.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/stores/chatStore.ts frontend/src/pages/Chat.tsx
git commit -m "feat(frontend): Chat page with SSE streaming, markdown, citation chips"
```

---

### Task 6: Dashboard Store + Dashboard Page

**Files:**
- Create: `frontend/src/stores/dashboardStore.ts`
- Rewrite: `frontend/src/pages/Dashboard.tsx`

- [ ] **Step 1: Create dashboardStore.ts**

`frontend/src/stores/dashboardStore.ts`:
```typescript
import { create } from 'zustand'
import axiosClient from '../api/axiosClient'
import { KPIValue } from '../types'

interface KPIs {
  revenue: KPIValue | null
  grossMargin: KPIValue | null
  ebitda: KPIValue | null
  netIncome: KPIValue | null
  cashBalance: KPIValue | null
  runway: KPIValue | null
}

interface DashboardState {
  kpis: KPIs
  loading: boolean
  lastUpdated: string | null
  fetchKPIs: () => Promise<void>
}

const KPI_QUERIES: { key: keyof KPIs; query: string; format: 'currency' | 'percent' | 'months' }[] = [
  { key: 'revenue', query: 'What is the latest total revenue? Reply with just the number.', format: 'currency' },
  { key: 'grossMargin', query: 'What is the current gross margin percentage? Reply with just the percentage.', format: 'percent' },
  { key: 'ebitda', query: 'What is the latest EBITDA? Reply with just the number.', format: 'currency' },
  { key: 'netIncome', query: 'What is the latest net income? Reply with just the number.', format: 'currency' },
  { key: 'cashBalance', query: 'What is the current cash balance? Reply with just the number.', format: 'currency' },
  { key: 'runway', query: 'What is the estimated cash runway in months? Reply with just the number.', format: 'months' },
]

function parseKPIResponse(text: string, format: string): KPIValue | null {
  // Extract first number from response
  const match = text.match(/[\$]?([\d,]+\.?\d*)\s*(%|months?|M|B|K)?/i)
  if (!match) return null

  const rawStr = match[1].replace(/,/g, '')
  const rawValue = parseFloat(rawStr)
  if (isNaN(rawValue)) return null

  let value: string
  const suffix = (match[2] || '').toLowerCase()

  if (format === 'currency') {
    if (rawValue >= 1_000_000_000) value = `$${(rawValue / 1_000_000_000).toFixed(1)}B`
    else if (rawValue >= 1_000_000) value = `$${(rawValue / 1_000_000).toFixed(1)}M`
    else if (rawValue >= 1_000) value = `$${(rawValue / 1_000).toFixed(0)}K`
    else value = `$${rawValue.toFixed(0)}`
  } else if (format === 'percent') {
    value = rawValue > 1 ? `${rawValue.toFixed(1)}%` : `${(rawValue * 100).toFixed(1)}%`
  } else {
    value = `${rawValue.toFixed(0)} months`
  }

  return { value, rawValue }
}

export const useDashboardStore = create<DashboardState>((set) => ({
  kpis: { revenue: null, grossMargin: null, ebitda: null, netIncome: null, cashBalance: null, runway: null },
  loading: false,
  lastUpdated: null,

  fetchKPIs: async () => {
    set({ loading: true })

    const results = await Promise.allSettled(
      KPI_QUERIES.map(async ({ key, query, format }) => {
        const res = await axiosClient.post('/chat/', {
          message: query,
          session_id: 'dashboard-kpi-session',
        })
        const parsed = parseKPIResponse(res.data.response, format)
        return { key, value: parsed }
      })
    )

    const kpis: KPIs = { revenue: null, grossMargin: null, ebitda: null, netIncome: null, cashBalance: null, runway: null }
    for (const result of results) {
      if (result.status === 'fulfilled' && result.value.value) {
        kpis[result.value.key] = result.value.value
      }
    }

    set({ kpis, loading: false, lastUpdated: new Date().toLocaleString() })
  },
}))
```

- [ ] **Step 2: Rewrite Dashboard.tsx**

`frontend/src/pages/Dashboard.tsx`:
```typescript
import { useEffect } from 'react'
import { Box, Card, CardContent, Grid, Typography, Skeleton, Button, Chip } from '@mui/material'
import TrendingUpIcon from '@mui/icons-material/TrendingUp'
import ChatIcon from '@mui/icons-material/Chat'
import UploadIcon from '@mui/icons-material/Upload'
import { useNavigate } from 'react-router-dom'
import { useDashboardStore } from '../stores/dashboardStore'
import { useDocumentStore } from '../stores/documentStore'
import { KPIValue } from '../types'

const KPI_CONFIG: { key: string; label: string }[] = [
  { key: 'revenue', label: 'Revenue' },
  { key: 'grossMargin', label: 'Gross Margin' },
  { key: 'ebitda', label: 'EBITDA' },
  { key: 'netIncome', label: 'Net Income' },
  { key: 'cashBalance', label: 'Cash Balance' },
  { key: 'runway', label: 'Runway' },
]

function KPICard({ label, data, loading }: { label: string; data: KPIValue | null; loading: boolean }) {
  if (loading) {
    return (
      <Card>
        <CardContent>
          <Skeleton width="40%" height={20} />
          <Skeleton width="70%" height={40} sx={{ mt: 1 }} />
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardContent>
        <Typography variant="body2" color="text.secondary">{label}</Typography>
        <Typography variant="h5" fontWeight={700} sx={{ mt: 0.5 }}>
          {data?.value ?? '—'}
        </Typography>
        {data?.change && (
          <Typography variant="caption" color={data.favorable ? 'secondary.main' : 'error.main'}>
            {data.change}
          </Typography>
        )}
      </CardContent>
    </Card>
  )
}

export default function Dashboard() {
  const navigate = useNavigate()
  const { kpis, loading, lastUpdated, fetchKPIs } = useDashboardStore()
  const { documents, fetchDocuments } = useDocumentStore()

  useEffect(() => { fetchDocuments() }, [fetchDocuments])

  useEffect(() => {
    if (documents.length > 0 && !lastUpdated) {
      fetchKPIs()
    }
  }, [documents, lastUpdated, fetchKPIs])

  const hasDocuments = documents.length > 0

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h5" fontWeight={600}>Dashboard</Typography>
          {lastUpdated && (
            <Typography variant="caption" color="text.secondary">Last updated: {lastUpdated}</Typography>
          )}
        </Box>
        {hasDocuments && (
          <Chip icon={<TrendingUpIcon />} label={`${documents.length} documents indexed`} variant="outlined" />
        )}
      </Box>

      {/* KPI Grid */}
      {hasDocuments ? (
        <Grid container spacing={2} sx={{ mb: 4 }}>
          {KPI_CONFIG.map(({ key, label }) => (
            <Grid item xs={12} sm={6} md={4} key={key}>
              <KPICard
                label={label}
                data={kpis[key as keyof typeof kpis]}
                loading={loading}
              />
            </Grid>
          ))}
        </Grid>
      ) : (
        <Card sx={{ mb: 4, textAlign: 'center', py: 6 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>No documents uploaded yet</Typography>
            <Typography color="text.secondary" sx={{ mb: 2 }}>
              Upload financial documents to populate your KPI dashboard
            </Typography>
            <Button variant="contained" startIcon={<UploadIcon />} onClick={() => navigate('/documents')}>
              Upload Documents
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Quick Actions */}
      <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>Quick Actions</Typography>
      <Box sx={{ display: 'flex', gap: 2 }}>
        <Button variant="outlined" startIcon={<ChatIcon />} onClick={() => navigate('/chat')}>
          Ask a Question
        </Button>
        <Button variant="outlined" startIcon={<UploadIcon />} onClick={() => navigate('/documents')}>
          Upload Documents
        </Button>
      </Box>
    </Box>
  )
}
```

- [ ] **Step 3: Verify**

```bash
cd frontend && npx tsc --noEmit && npm run dev
```

Open `http://localhost:5173/dashboard`. Verify: empty state shows "No documents uploaded yet" with Upload button. After uploading a document: KPI cards show skeleton loading, then populate with values from Claude responses.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/stores/dashboardStore.ts frontend/src/pages/Dashboard.tsx
git commit -m "feat(frontend): Dashboard page with auto-populated KPI cards"
```

---

### Task 7: CORS Fix + Final Verification + Push

**Files:**
- Modify: `backend/api/main.py` (add CORS middleware)

- [ ] **Step 1: Add CORS to FastAPI**

The frontend runs on `localhost:5173`, the backend on `localhost:8000`. Add CORS middleware to `backend/api/main.py`.

Add import after existing imports:
```python
from fastapi.middleware.cors import CORSMiddleware
```

Add after `app = FastAPI(...)`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- [ ] **Step 2: Verify end-to-end**

Start all services:
```bash
# Terminal 1: Redis
docker start redis-finsight

# Terminal 2: Backend
cd finsight-cfo && conda activate finsight && PYTHONPATH=. uvicorn backend.api.main:app --reload --port 8000

# Terminal 3: Frontend
cd finsight-cfo/frontend && npm run dev
```

Open `http://localhost:5173`. Test:
1. Navigate between all 3 pages via sidebar
2. Toggle dark/light theme
3. Collapse/expand sidebar
4. Upload a document on `/documents`
5. Ask a question on `/chat`, see streaming indicator + response with citations
6. Navigate to `/dashboard`, see KPI cards loading

- [ ] **Step 3: Run backend tests (no regressions)**

```bash
cd backend && conda run -n finsight pytest tests/ -v -k "not integration"
```

Expected: all 224 tests pass.

- [ ] **Step 4: Build frontend for production**

```bash
cd frontend && npm run build
```

Expected: no errors.

- [ ] **Step 5: Commit + push**

```bash
git add -A
git commit -m "feat(frontend): Phase 5 complete — Dashboard, Chat, Documents MVP"
git push
```

---

## Self-Review

**Spec coverage:**
- [x] Dark mode + light/dark toggle — Task 1 (muiTheme.ts + sessionStore)
- [x] Purple accent, green/red colors — Task 1 (muiTheme.ts)
- [x] Sidebar (collapsible, 3 nav items, theme toggle) — Task 2
- [x] Routing (/dashboard, /chat, /documents, / redirect) — Task 2
- [x] Documents: DataGrid, upload dialog, delete confirm — Task 3
- [x] Chat: SSE streaming, markdown, citation chips, thinking indicator — Tasks 4-5
- [x] Dashboard: 6 KPI cards, auto-populated, skeleton loading, empty state — Task 6
- [x] Zustand stores (session, document, chat, dashboard) — Tasks 1, 3, 5, 6
- [x] Axios client — Task 1
- [x] CORS middleware — Task 7
- [x] Error handling per page (as spec'd) — Tasks 3, 5, 6

**No placeholders found.** All code is complete.

**Type consistency:** `Document`, `ChatMessage`, `KPIValue` interfaces defined in Task 1, used consistently in stores and pages. Store method names match spec (`fetchDocuments`, `sendMessage`, `fetchKPIs`, etc.).
