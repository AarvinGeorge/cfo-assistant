/**
 * sessionStore.ts
 *
 * Zustand store for global session state — theme mode, panel visibility,
 * and session ID. Persisted to localStorage.
 *
 * Role in project:
 *   Global UI state. The only store persisted between page reloads (key:
 *   "finsight-session"). Controls the 3-panel layout and the active MUI
 *   theme. Read by App.tsx (panel widths), main.tsx (theme), and the
 *   chat store (session ID for LangGraph thread continuity).
 *
 * Main parts:
 *   - SessionState: interface with themeMode, leftPanelOpen, rightPanelOpen,
 *     sessionId, and their toggle/setter actions.
 *   - useSessionStore: Zustand store with persist middleware writing to
 *     localStorage under the key "finsight-session".
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface SessionState {
  themeMode: 'dark' | 'light'
  sessionId: string
  leftPanelOpen: boolean
  rightPanelOpen: boolean
  toggleTheme: () => void
  setSessionId: (id: string) => void
  toggleLeftPanel: () => void
  toggleRightPanel: () => void
}

export const useSessionStore = create<SessionState>()(
  persist(
    (set) => ({
      themeMode: 'dark',
      sessionId: crypto.randomUUID(),
      leftPanelOpen: true,
      rightPanelOpen: true,
      toggleTheme: () =>
        set((s) => ({ themeMode: s.themeMode === 'dark' ? 'light' : 'dark' })),
      setSessionId: (id: string) => set({ sessionId: id }),
      toggleLeftPanel: () => set((s) => ({ leftPanelOpen: !s.leftPanelOpen })),
      toggleRightPanel: () => set((s) => ({ rightPanelOpen: !s.rightPanelOpen })),
    }),
    { name: 'finsight-session' }
  )
)
