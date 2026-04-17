/**
 * main.tsx
 *
 * React application entry point — mounts the Root component into the DOM.
 *
 * Role in project:
 *   Top-level bootstrap. Vite loads this file first. It wraps the App
 *   component in MUI ThemeProvider and CssBaseline, reading the active
 *   theme from sessionStore so the correct theme is applied on first paint
 *   with no flash of wrong theme.
 *
 * Main parts:
 *   - Root: functional component that reads themeMode from sessionStore and
 *     passes the matching MUI theme (darkTheme or lightTheme) to ThemeProvider.
 *   - ReactDOM.createRoot: mounts Root into the #root div in index.html.
 */
import React from 'react'
import ReactDOM from 'react-dom/client'
import { ThemeProvider, CssBaseline } from '@mui/material'
import { useSessionStore } from './stores/sessionStore'
import { darkTheme, lightTheme } from './theme/muiTheme'
import App from './App'

function Root() {
  const themeMode = useSessionStore((s) => s.themeMode)
  const theme = themeMode === 'dark' ? darkTheme : lightTheme

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <App />
    </ThemeProvider>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
)
