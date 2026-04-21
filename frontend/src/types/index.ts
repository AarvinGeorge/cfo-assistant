/**
 * types/index.ts
 *
 * Shared TypeScript interfaces and enums used across the entire frontend.
 *
 * Role in project:
 *   Type contract layer. All API response shapes, store state shapes, and
 *   component prop types are defined here so the compiler catches mismatches
 *   between the backend API surface and frontend usage.
 *
 * Main parts:
 *   - Document: shape of a document record returned by GET /documents/.
 *   - Workspace: shape of a workspace record returned by GET /workspaces/.
 *   - ChatMessage: a single message in the conversation (role, content, citations).
 *   - Citation: a parsed [Source: ...] reference with doc name and section.
 *   - KPIValue: a single KPI card value (label, value, format, change, favorable).
 *   - KpiEntry: a single cached KPI entry returned by GET /kpis/.
 *   - KpisResponse: full response shape from GET /kpis/.
 *   - StreamEvent: discriminated union of SSE event types emitted by /chat/stream.
 *   - Intent: enum of the 7 intent categories the orchestrator classifies into.
 */
export interface Workspace {
  id: string
  name: string
  description: string | null
  status: 'active' | 'archived'
  created_at: string
  updated_at: string
}

export interface Document {
  doc_id: string
  doc_name: string
  doc_type: string
  fiscal_year: string
  chunk_count: number
  status: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'error'
  content: string
  intent?: string
  citations?: string[]
  timestamp: number
}

export interface KPIValue {
  value: string
  rawValue: number
  change?: string
  favorable?: boolean
}

export interface HealthStatus {
  status: string
  redis: boolean
  pinecone: boolean
  anthropic_key: boolean
  gemini_key: boolean
}

export interface KpiEntry {
  response: string       // raw Claude response (fallback for malformed parses)
  citations: string[]
  computed_at: string    // ISO timestamp
  headline: string       // e.g. "$22.6B" or "45.2%" — parsed by backend
  period: string         // e.g. "FY2025" — parsed by backend
  note: string           // e.g. "+13% YoY" — parsed by backend
}

export interface KpisResponse {
  kpis: Record<string, KpiEntry> | null
  status: 'ready' | 'empty'
  computed_at: string | null
  cache_hit: boolean
}
