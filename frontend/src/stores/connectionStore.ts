/**
 * connectionStore.ts
 *
 * Zustand store tracking whether the FastAPI backend is reachable.
 *
 * Role in project:
 *   Frontend state layer. Flipped by the axios response interceptor on every
 *   API call — true on ERR_NETWORK / Network Error, false on any HTTP
 *   response (including 4xx/5xx, which still proves the backend is up).
 *   Consumed by BackendUnreachableModal, which renders a blocking dialog
 *   when the flag is true so users see exactly what's wrong instead of a
 *   generic "Upload failed" toast.
 *
 * Main parts:
 *   - ConnectionState: interface with backendUnreachable flag + setter
 *   - useConnectionStore: Zustand store (not persisted — state is session-local)
 */
import { create } from 'zustand'

interface ConnectionState {
  backendUnreachable: boolean
  setBackendUnreachable: (unreachable: boolean) => void
}

export const useConnectionStore = create<ConnectionState>((set) => ({
  backendUnreachable: false,
  setBackendUnreachable: (unreachable) => set({ backendUnreachable: unreachable }),
}))
