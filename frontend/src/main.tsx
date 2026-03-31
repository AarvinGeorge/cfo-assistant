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
