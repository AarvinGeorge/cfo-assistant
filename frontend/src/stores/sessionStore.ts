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
