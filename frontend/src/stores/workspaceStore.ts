/**
 * workspaceStore.ts
 *
 * Zustand store managing the list of workspaces and workspace creation.
 * The "active workspace" is NOT tracked here — that's sessionStore.workspaceId,
 * which is persisted to localStorage.
 *
 * Role in project:
 *   Workspace feature state. Owned by WorkspaceSwitcher. fetchWorkspaces()
 *   is called once on mount from App.tsx to populate the dropdown.
 *
 * Main parts:
 *   - WorkspaceState: workspaces array, loading flag, error string.
 *   - fetchWorkspaces(): GET /workspaces/ and populates the store.
 *   - createWorkspace(): POST /workspaces/ and appends to the local list,
 *     returning the new workspace so callers can auto-switch.
 */
import { create } from 'zustand'
import axiosClient from '../api/axiosClient'
import { Workspace } from '../types'

interface WorkspaceState {
  workspaces: Workspace[]
  loading: boolean
  error: string | null
  fetchWorkspaces: () => Promise<void>
  createWorkspace: (name: string, description?: string) => Promise<Workspace>
}

export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
  workspaces: [],
  loading: false,
  error: null,

  fetchWorkspaces: async () => {
    set({ loading: true, error: null })
    try {
      const res = await axiosClient.get<Workspace[]>('/workspaces/')
      set({ workspaces: res.data, loading: false })
    } catch (err: any) {
      set({
        workspaces: [],
        loading: false,
        error: err?.message ?? 'Failed to load workspaces',
      })
    }
  },

  createWorkspace: async (name: string, description?: string) => {
    const res = await axiosClient.post<Workspace>('/workspaces/', {
      name,
      description: description || null,
    })
    const newWorkspace = res.data
    set({ workspaces: [...get().workspaces, newWorkspace] })
    return newWorkspace
  },
}))
