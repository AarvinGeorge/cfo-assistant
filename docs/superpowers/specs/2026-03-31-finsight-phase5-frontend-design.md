# FinSight CFO Assistant — Phase 5: Frontend Design Spec

**Master reference:** `CLAUDE.md` (project vision, conventions, tech stack, API surface)

---

## Scope

MVP frontend with 3 pages: Dashboard, Chat, Documents. Built with React 18 + TypeScript + MUI v6 + Zustand + Vite. Connects to the existing FastAPI backend at `localhost:8000`.

Pages deferred to later: Model Studio, Scenario Planner, Reports. Their backend APIs are accessible from the Chat interface.

---

## Visual Style

- **Dark mode default** with light/dark toggle persisted to localStorage
- **Primary accent:** `#7c4dff` (purple)
- **Favorable/positive:** `#00e676` (green)
- **Unfavorable/negative:** `#ff5252` (red)
- **Surface colors (dark):** background `#1a1a2e`, surface `#1e1e2f`, elevated `#2a2a40`
- **Surface colors (light):** background `#f5f5f5`, surface `#ffffff`, elevated `#f8f9fa`
- **Border radius:** 12px globally
- **Font:** Inter (via Google Fonts) with system font fallback
- **Aesthetic:** Modern SaaS (Notion/Linear feel)

---

## Layout Shell

**Sidebar (persistent, collapsible):**
- Expanded: 240px, shows icon + label
- Collapsed: 64px, shows icon only
- Contents: FinSight logo at top, 3 nav items (Dashboard, Chat, Documents), theme toggle at bottom, collapse toggle
- Active nav item highlighted with purple accent background
- Sidebar collapse state persisted to localStorage via `sessionStore`

**Main content area:**
- Fills remaining width
- No top bar — page titles are inside each page's content area

**Routing:**
- `/dashboard` — Dashboard page
- `/chat` — Chat page
- `/documents` — Documents page
- `/` redirects to `/dashboard`

---

## Page 1: Documents (`/documents`)

**Purpose:** Upload, view, and manage ingested financial documents.

**Header bar:**
- Left: "Documents" title (h4 typography)
- Right: "+ Upload" MUI Button (purple, contained)

**Search:**
- MUI TextField below header, full width, outlined variant
- Client-side filter on document name (instant, no debounce needed)

**Document table:**
- MUI DataGrid with columns:
  - Name (string, flex: 2)
  - Type (string, flex: 1) — e.g., "10-K", "Income Statement", "Budget"
  - Fiscal Year (string, flex: 1)
  - Chunks (number, flex: 0.5)
  - Status (rendered as MUI Chip: green "Indexed", yellow "Processing")
  - Actions (flex: 0.5) — delete IconButton with MUI trash icon
- Delete triggers a confirmation Dialog before calling `DELETE /documents/{doc_id}`
- Empty state: "No documents uploaded yet. Click + Upload to get started."

**Upload dialog (MUI Dialog):**
- File picker (accepts .pdf, .csv, .txt, .html)
- Doc type dropdown (MUI Select): 10-K, 10-Q, Income Statement, Balance Sheet, Cash Flow Statement, Budget, Board Report, General
- Fiscal year text field (MUI TextField)
- "Upload" button calls `POST /documents/upload` (multipart form)
- MUI LinearProgress shown during upload + processing
- On success: close dialog, refresh document list, show success Snackbar
- On error: show error message inside the dialog (not a toast)

**Data source:** `GET /documents/`

**Zustand store — `documentStore`:**
```typescript
{
  documents: Document[]
  loading: boolean
  fetchDocuments: () => Promise<void>
  uploadDocument: (file: File, docType: string, fiscalYear: string) => Promise<void>
  deleteDocument: (docId: string) => Promise<void>
}
```

---

## Page 2: Chat (`/chat`)

**Purpose:** Natural language Q&A with the CFO assistant. Core feature.

**Message area:**
- Full viewport height minus input bar
- Scrollable, auto-scrolls to bottom on new messages
- Assistant messages: left-aligned, dark surface background (`#1e1e2f`), rounded bubble
- User messages: right-aligned, purple tint background, rounded bubble
- Assistant messages render Markdown via `react-markdown`: tables, bullet points, bold, code blocks
- Tables in Markdown styled with MUI Table components

**Citation chips:**
- Pattern `[Source: doc_name, section, page]` in response text parsed and rendered as small MUI Chips (purple outline variant, small size)
- Chips are inline within the message text, not extracted to a separate area
- Non-clickable for MVP (clicking to jump to source document is a future feature)

**Streaming (SSE):**
- Uses native `fetch` to `POST /chat/stream` (Axios doesn't handle SSE)
- SSE events update the UI progressively:
  - `session` → store session_id
  - `intent` → update thinking indicator ("Classifying as document_qa...")
  - `retrieval` → update thinking indicator ("Retrieved 5 relevant chunks...")
  - `model_output` → update thinking indicator ("Running financial model...")
  - `response` → render the full response text as assistant message
  - `done` → finalize message, parse citation chips
  - `error` → show error message bubble
- Thinking indicator: MUI CircularProgress (small, 20px) with dynamic label text, shown between user message and the incoming response

**Input bar:**
- Pinned to bottom of chat area
- MUI TextField (outlined, multiline, max 3 rows)
- Send IconButton (purple) on the right
- Enter sends, Shift+Enter for newline
- Disabled while streaming (prevent double-send)

**Session management:**
- `session_id` generated on first message, stored in `sessionStore` (localStorage)
- "New Chat" button in the chat header area resets `session_id` and clears message list
- Conversation history managed by LangGraph checkpointer on the backend

**Empty state:** Centered welcome message: "Hello! I'm FinSight, your financial intelligence assistant. Upload documents and ask me anything about your company's financial performance."

**Zustand store — `chatStore`:**
```typescript
{
  messages: ChatMessage[]
  isStreaming: boolean
  currentIntent: string
  sendMessage: (message: string) => Promise<void>
  clearChat: () => void
}
```

---

## Page 3: Dashboard (`/dashboard`)

**Purpose:** At-a-glance KPI overview and navigation hub.

**Header:**
- "Dashboard" title
- Subtitle: "Last updated: [timestamp]" + "[N] documents indexed" badge

**KPI cards (MUI Grid, 2 rows x 3 columns):**
- 6 cards: Revenue, Gross Margin, EBITDA, Net Income, Cash Balance, Runway
- Each card (MUI Card) contains:
  - Label (small, muted text)
  - Value (large, bold — formatted: `$10.2M`, `45.2%`, `18 months`)
  - Period change (small text with arrow icon: green up-arrow + percentage for favorable, red down-arrow for unfavorable)
- Cards show MUI Skeleton while loading

**KPI population:**
- On mount, if documents exist (check `documentStore`), fire 6 parallel `POST /chat/` calls with preset queries:
  1. "What is the latest total revenue? Reply with just the number."
  2. "What is the current gross margin percentage? Reply with just the number."
  3. "What is the latest EBITDA? Reply with just the number."
  4. "What is the latest net income? Reply with just the number."
  5. "What is the current cash balance? Reply with just the number."
  6. "What is the estimated cash runway in months? Reply with just the number."
- Use a dedicated session_id (`dashboard-kpi-session`) separate from the chat session
- Parse numeric values from responses (regex: extract first dollar amount or percentage or plain number)
- Cache results in `dashboardStore` — don't re-fetch on every navigation, only on manual refresh or new document upload
- If a query fails, that specific KPI card shows "Unable to load"

**Empty state (no documents):**
- KPI cards replaced with a single centered card: "Upload financial documents to see your KPI dashboard"
- Quick-action buttons still shown

**Quick-action buttons (below KPI grid):**
- "Ask a Question" → navigates to `/chat`
- "Upload Documents" → navigates to `/documents`

**Zustand store — `dashboardStore`:**
```typescript
{
  kpis: {
    revenue: KPIValue | null
    grossMargin: KPIValue | null
    ebitda: KPIValue | null
    netIncome: KPIValue | null
    cashBalance: KPIValue | null
    runway: KPIValue | null
  }
  loading: boolean
  lastUpdated: string | null
  fetchKPIs: () => Promise<void>
}

type KPIValue = {
  value: string       // formatted display value
  rawValue: number    // parsed number
  change?: string     // "+5.2%" or "-3.1%"
  favorable?: boolean
}
```

---

## Shared Infrastructure

**Axios client (`api/axiosClient.ts`):**
- Base URL: `http://localhost:8000`
- Response interceptor: on 4xx/5xx, log error. Individual call sites handle their own error UI.
- No auth headers (local-first)

**SSE client (in `chatStore`):**
- Native `fetch` with `ReadableStream` reader
- Parses `data: {...}\n\n` lines
- Reconnection: not needed for MVP (user can re-send message)

**Theme (`theme/muiTheme.ts`):**
- Two themes: `darkTheme` and `lightTheme`
- `sessionStore.themeMode` controls which is active
- MUI `ThemeProvider` wraps `App.tsx` with the active theme
- `CssBaseline` for global reset

**Error handling:**
- Documents: upload errors shown in dialog, fetch errors show empty DataGrid
- Chat: SSE errors shown as error message bubble, network failure shows "Connection lost"
- Dashboard: individual KPI card failures show "Unable to load", don't break other cards
- Loading: MUI Skeleton components (not spinners) for all loading states

---

## Dependencies to Add

Add to `package.json`:
- `react-markdown` — Markdown rendering for assistant messages
- `remark-gfm` — GitHub Flavored Markdown (tables, strikethrough)

---

## File Structure

```
frontend/src/
├── main.tsx                          # ReactDOM.createRoot, ThemeProvider, RouterProvider
├── App.tsx                           # Layout shell (Sidebar + RouterOutlet)
├── theme/
│   └── muiTheme.ts                   # Dark + light MUI themes
├── api/
│   └── axiosClient.ts                # Axios instance, base URL, interceptor
├── stores/
│   ├── sessionStore.ts               # theme mode, session_id, sidebar state
│   ├── chatStore.ts                  # messages, streaming, sendMessage
│   ├── documentStore.ts              # documents, upload, delete
│   └── dashboardStore.ts             # KPI values, fetchKPIs
├── pages/
│   ├── Dashboard.tsx
│   ├── Chat.tsx
│   └── DocumentManager.tsx
├── components/
│   ├── layout/
│   │   └── Sidebar.tsx
│   ├── chat/
│   │   ├── ChatBubble.tsx            # Message bubble with Markdown + citations
│   │   ├── CitationChip.tsx          # Inline [Source: ...] chip
│   │   └── StreamingIndicator.tsx    # Thinking/loading indicator
│   └── common/                       # Grows organically as components are reused
└── types/
    └── index.ts                      # Shared TypeScript interfaces
```

---

## Out of Scope for Phase 5

- Model Studio page (`/models`)
- Scenario Planner page (`/scenarios`)
- Reports page (`/reports`)
- Plotly chart rendering (deferred — no charts in MVP pages)
- File preview / document detail panel
- User authentication
- Mobile responsiveness (desktop-first)
- Token-level streaming (current SSE streams node completions; true token streaming is a Phase 6 improvement)
