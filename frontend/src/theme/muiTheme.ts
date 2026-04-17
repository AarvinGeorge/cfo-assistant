/**
 * muiTheme.ts
 *
 * MUI v6 theme definitions for FinSight — dark and light variants with
 * a shared design token set.
 *
 * Role in project:
 *   Visual foundation. Consumed by main.tsx ThemeProvider. All colours,
 *   typography, spacing, and component overrides are defined here so the
 *   rest of the application uses semantic tokens (primary.main, action.selected)
 *   rather than hardcoded hex values.
 *
 * Main parts:
 *   - designTokens: raw colour values for dark and light modes (bg, surface,
 *     elevated, accent, favorable, unfavorable).
 *   - darkTheme: MUI theme with dark palette wired to designTokens, including
 *     action.selected set to elevated (#3A3A3C) for active state consistency.
 *   - lightTheme: MUI theme with light palette counterpart.
 */
import { createTheme } from '@mui/material/styles'

// Design tokens matching the Figma design (NotebookLM-inspired neutral dark)
export const designTokens = {
  dark: {
    bg: '#1C1C1E',         // near-black background
    surface: '#2C2C2E',    // panel/card surfaces
    elevated: '#3A3A3C',   // hover states, selected items
    border: 'rgba(255,255,255,0.08)',
    textPrimary: '#F5F5F7',
    textSecondary: '#8E8E93',
    accent: '#7c4dff',
    green: '#10B964',
    red: '#FF5252',
  },
  light: {
    bg: '#F2F2F7',
    surface: '#FFFFFF',
    elevated: '#E5E5EA',
    border: 'rgba(0,0,0,0.08)',
    textPrimary: '#1C1C1E',
    textSecondary: '#6E6E73',
    accent: '#7c4dff',
    green: '#34C759',
    red: '#FF3B30',
  },
}

const sharedTypography = {
  fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
  fontSize: 14,
}

const sharedShape = {
  borderRadius: 10,
}

const sharedComponents = {
  MuiCard: {
    styleOverrides: {
      root: { backgroundImage: 'none' },
    },
  },
  MuiButton: {
    styleOverrides: {
      root: { textTransform: 'none' as const, fontWeight: 600, borderRadius: 8 },
    },
  },
  MuiChip: {
    styleOverrides: {
      root: { borderRadius: 6 },
    },
  },
}

export const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: '#7c4dff' },
    secondary: { main: '#10B964' },
    error: { main: '#FF5252' },
    background: {
      default: '#1C1C1E',
      paper: '#2C2C2E',
    },
    divider: 'rgba(255,255,255,0.08)',
    text: {
      primary: '#F5F5F7',
      secondary: '#8E8E93',
    },
    action: {
      hover: 'rgba(255,255,255,0.06)',
      selected: '#3A3A3C',   // elevated token
      disabledBackground: 'rgba(255,255,255,0.08)',
      disabled: 'rgba(255,255,255,0.30)',
    },
  },
  typography: sharedTypography,
  shape: sharedShape,
  components: sharedComponents,
})

export const lightTheme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: '#7c4dff' },
    secondary: { main: '#34C759' },
    error: { main: '#FF3B30' },
    background: {
      default: '#F2F2F7',
      paper: '#FFFFFF',
    },
    divider: 'rgba(0,0,0,0.08)',
    text: {
      primary: '#1C1C1E',
      secondary: '#6E6E73',
    },
    action: {
      hover: 'rgba(0,0,0,0.05)',
      selected: '#E5E5EA',   // elevated token
      disabledBackground: 'rgba(0,0,0,0.06)',
      disabled: 'rgba(0,0,0,0.30)',
    },
  },
  typography: sharedTypography,
  shape: sharedShape,
  components: sharedComponents,
})
