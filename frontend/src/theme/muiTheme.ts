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
