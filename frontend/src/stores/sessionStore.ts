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
