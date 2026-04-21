/**
 * dashboardStore.ts
 *
 * Zustand store managing the KPI dashboard state. Fetches 6 KPIs in one
 * call from GET /kpis/ (SQLite-cached, 24h TTL on the backend). No more
 * direct chat calls from the frontend.
 *
 * Role in project:
 *   KPI dashboard state. Owned by RightPanel. fetchKPIs() is called from
 *   App.tsx on mount and whenever sessionStore.workspaceId changes.
 *
 * Main parts:
 *   - DashboardState: kpis (record keyed by kpi_key), status, computedAt,
 *     loading, error, cacheHit.
 *   - fetchKPIs(forceRefresh?): calls GET /kpis/ with optional ?refresh=true.
 *   - status 'empty' means the workspace has zero documents; RightPanel
 *     renders an "Upload a document" prompt in this case.
 *   - loading: derived boolean (true when status === 'loading') kept for
 *     backward compatibility with any consumers that read it directly.
 *   - lastUpdated: alias for computedAt, kept for backward compatibility.
 */
import { create } from 'zustand'
import axiosClient from '../api/axiosClient'
import { KpiEntry, KpisResponse } from '../types'

interface DashboardState {
  kpis: Record<string, KpiEntry> | null
  status: 'loading' | 'ready' | 'empty' | 'error'
  computedAt: string | null
  cacheHit: boolean
  error: string | null
  /** @deprecated Use status === 'loading' instead. Kept for backward compat. */
  loading: boolean
  /** @deprecated Use computedAt instead. Kept for backward compat. */
  lastUpdated: string | null
  fetchKPIs: (forceRefresh?: boolean) => Promise<void>
}

export const useDashboardStore = create<DashboardState>((set) => ({
  kpis: null,
  status: 'loading',
  computedAt: null,
  cacheHit: false,
  error: null,
  loading: true,
  lastUpdated: null,

  fetchKPIs: async (forceRefresh = false) => {
    set({ status: 'loading', loading: true, error: null })
    try {
      const res = await axiosClient.get<KpisResponse>(
        `/kpis/${forceRefresh ? '?refresh=true' : ''}`
      )
      set({
        kpis: res.data.kpis,
        status: res.data.status,  // 'ready' | 'empty'
        computedAt: res.data.computed_at,
        cacheHit: res.data.cache_hit,
        loading: false,
        lastUpdated: res.data.computed_at,
      })
    } catch (err: unknown) {
      const error =
        (err as { response?: { data?: { detail?: string } }; message?: string })
          ?.response?.data?.detail ??
        (err as { message?: string })?.message ??
        'Failed to load KPIs'
      set({
        kpis: null,
        status: 'error',
        computedAt: null,
        cacheHit: false,
        loading: false,
        lastUpdated: null,
        error,
      })
    }
  },
}))
