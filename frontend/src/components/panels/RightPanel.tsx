/**
 * RightPanel.tsx
 *
 * Right panel of the 3-panel layout — the Studio panel showing live KPI
 * cards and quick-action shortcuts.
 *
 * Role in project:
 *   CFO dashboard surface. Reads from dashboardStore (KPI values from
 *   GET /kpis/, status, computedAt) and chatStore (sendMessage for Quick
 *   Actions). fetchKPIs() is called from App.tsx on mount and workspace
 *   change — not locally. Collapses to a 48px icon rail.
 *
 * Main parts:
 *   - RightPanel: expanded/collapsed render paths.
 *   - KPI grid: 6 cards (Revenue, Gross Margin, EBITDA, Net Income, Cash
 *     Balance, Runway) in a 2-column MUI Grid with skeleton loaders.
 *   - Quick Actions: 4 MUI Buttons (DCF Model, Scenario Analysis, Forecast
 *     Revenue, Export Report) that call sendMessage() with preset prompts.
 *   - timeAgo: inline helper to format ISO timestamps as relative strings.
 *   - TODO: migrate Grid to Grid2 for MUI v7 compatibility.
 */
import {
  Box, Typography, IconButton, Tooltip, Grid, Skeleton,
  Card, CardContent, Button, Divider,
} from '@mui/material'
import RefreshIcon from '@mui/icons-material/Refresh'
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft'
import ChevronRightIcon from '@mui/icons-material/ChevronRight'
import ShowChartIcon from '@mui/icons-material/ShowChart'
import ScatterPlotIcon from '@mui/icons-material/ScatterPlot'
import TimelineIcon from '@mui/icons-material/Timeline'
import DownloadIcon from '@mui/icons-material/Download'
import DashboardIcon from '@mui/icons-material/Dashboard'
import { useDashboardStore } from '../../stores/dashboardStore'
import { useSessionStore } from '../../stores/sessionStore'
import { useChatStore } from '../../stores/chatStore'
import { KpiEntry } from '../../types'

// Backend kpi_key values mapped to display labels, in display order
const KPI_CONFIG: { key: string; label: string }[] = [
  { key: 'revenue', label: 'Revenue' },
  { key: 'gross_margin', label: 'Gross Margin' },
  { key: 'ebitda', label: 'EBITDA' },
  { key: 'net_income', label: 'Net Income' },
  { key: 'cash_balance', label: 'Cash Balance' },
  { key: 'runway', label: 'Runway' },
]

const QUICK_ACTIONS = [
  {
    label: 'Run DCF Model',
    sub: 'Discounted cash flow valuation',
    icon: <ShowChartIcon fontSize="small" />,
    message: 'Run a DCF valuation model based on the available financial data. Show the key assumptions and output.',
  },
  {
    label: 'Scenario Analysis',
    sub: 'Bull / Base / Bear scenarios',
    icon: <ScatterPlotIcon fontSize="small" />,
    message: 'Run a bull, base, and bear scenario analysis. Show revenue, EBITDA and cash runway under each scenario.',
  },
  {
    label: 'Forecast Revenue',
    sub: '12-month projection',
    icon: <TimelineIcon fontSize="small" />,
    message: 'Generate a 12-month revenue forecast based on historical trends in the uploaded documents.',
  },
  {
    label: 'Export Report',
    sub: 'Boardroom-ready summary',
    icon: <DownloadIcon fontSize="small" />,
    message: 'Summarize all key financial metrics, trends, and insights in a boardroom-ready format.',
  },
]

function timeAgo(iso: string | null): string {
  if (!iso) return ''
  const then = new Date(iso).getTime()
  const now = Date.now()
  const diffMin = Math.floor((now - then) / 60000)
  if (diffMin < 1) return 'just now'
  if (diffMin === 1) return '1 min ago'
  if (diffMin < 60) return `${diffMin} min ago`
  const hours = Math.floor(diffMin / 60)
  if (hours === 1) return '1 hour ago'
  if (hours < 24) return `${hours} hours ago`
  return `${Math.floor(hours / 24)} day(s) ago`
}

function KPICard({ label, data, loading }: { label: string; data: KpiEntry | null | undefined; loading: boolean }) {
  if (loading) {
    return (
      <Card variant="outlined" sx={{ bgcolor: 'action.hover', border: 'none' }}>
        <CardContent sx={{ p: '10px !important' }}>
          <Skeleton width="60%" height={12} />
          <Skeleton width="80%" height={22} sx={{ mt: 0.5 }} />
          <Skeleton width="50%" height={12} sx={{ mt: 0.25 }} />
        </CardContent>
      </Card>
    )
  }

  // Use the parsed headline/period/note from the backend (parse_kpi_response).
  // Fall back to truncated raw response if somehow the parser produced nothing
  // (e.g. legacy cached entries from before the prompt-format change).
  const headline = data?.headline?.trim() || (
    data?.response ? (data.response.length > 40 ? data.response.slice(0, 40) + '…' : data.response) : '—'
  )
  const period = data?.period?.trim() || ''
  const note = data?.note?.trim() || ''

  // Full response shown on hover via native title tooltip — useful when the
  // parsed headline is terse and the user wants the full analysis.
  const tooltip = data?.response?.trim() || undefined

  return (
    <Card
      variant="outlined"
      sx={{ bgcolor: 'action.hover', border: 'none' }}
      title={tooltip}
    >
      <CardContent sx={{ p: '10px !important' }}>
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ fontSize: 10, fontWeight: 500, letterSpacing: '0.04em' }}
        >
          {label.toUpperCase()}
        </Typography>
        <Typography
          variant="body1"
          fontWeight={700}
          sx={{ lineHeight: 1.2, mt: 0.25, fontSize: 18 }}
          noWrap
        >
          {headline}
        </Typography>
        {(period || note) && (
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ fontSize: 10, display: 'block', mt: 0.25, lineHeight: 1.3 }}
          >
            {period}
            {period && note ? ' · ' : ''}
            {note}
          </Typography>
        )}
      </CardContent>
    </Card>
  )
}

export default function RightPanel() {
  const { kpis, status, computedAt, fetchKPIs } = useDashboardStore()
  const { rightPanelOpen, toggleRightPanel } = useSessionStore()
  const { sendMessage } = useChatStore()

  const isLoading = status === 'loading'

  const handleQuickAction = (message: string) => {
    sendMessage(message)
  }

  const handleRefresh = () => {
    fetchKPIs(true)
  }

  // ── Collapsed rail ─────────────────────────────────────────
  if (!rightPanelOpen) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', height: '100%', py: 1 }}>
        <Tooltip title="Expand Studio" placement="left">
          <IconButton size="small" onClick={toggleRightPanel} sx={{ mb: 2, mt: 1 }}>
            <ChevronLeftIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title="Studio" placement="left">
          <IconButton size="small" sx={{ mb: 1, color: 'primary.main' }}>
            <DashboardIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title="Run DCF" placement="left">
          <IconButton size="small" sx={{ mb: 1 }} onClick={() => handleQuickAction(QUICK_ACTIONS[0].message)}>
            <ShowChartIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title="Scenario Analysis" placement="left">
          <IconButton size="small" sx={{ mb: 1 }} onClick={() => handleQuickAction(QUICK_ACTIONS[1].message)}>
            <ScatterPlotIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title="Forecast Revenue" placement="left">
          <IconButton size="small" onClick={() => handleQuickAction(QUICK_ACTIONS[2].message)}>
            <TimelineIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>
    )
  }

  // ── Expanded panel ─────────────────────────────────────────
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', minWidth: 0 }}>
      {/* Header */}
      <Box
        sx={{
          display: 'flex', alignItems: 'center', px: 2, height: 56,
          borderBottom: '1px solid', borderColor: 'divider', flexShrink: 0,
        }}
      >
        <Tooltip title="Collapse panel">
          <IconButton size="small" onClick={toggleRightPanel} sx={{ mr: 1 }}>
            <ChevronRightIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Typography variant="body1" fontWeight={600} sx={{ flex: 1 }}>Studio</Typography>
        <Tooltip title="Refresh KPIs">
          <span>
            <IconButton size="small" onClick={handleRefresh} disabled={isLoading} aria-label="Refresh KPIs">
              <RefreshIcon fontSize="small" />
            </IconButton>
          </span>
        </Tooltip>
      </Box>

      {/* Scrollable content */}
      <Box sx={{ flex: 1, overflowY: 'auto', px: 1.5, py: 1.5 }}>

        {/* Financial Overview */}
        <Typography
          variant="caption"
          sx={{ px: 0.5, pb: 1, display: 'block', color: 'text.secondary', fontWeight: 600, letterSpacing: '0.08em' }}
        >
          FINANCIAL OVERVIEW
        </Typography>

        {/* Empty state: workspace has no documents */}
        {status === 'empty' && (
          <Box sx={{ textAlign: 'center', py: 3, px: 1 }}>
            <Typography variant="body2" sx={{ fontSize: 12, color: 'primary.main' }}>
              Upload a document to see KPIs.
            </Typography>
          </Box>
        )}

        {/* Error state */}
        {status === 'error' && (
          <Box sx={{ textAlign: 'center', py: 3, px: 1 }}>
            <Typography variant="body2" color="error" sx={{ fontSize: 12 }}>
              Failed to load KPIs. Try refreshing.
            </Typography>
          </Box>
        )}

        {/* Loading or ready: show the 6 KPI cards */}
        {(isLoading || status === 'ready') && (
          <Grid container spacing={1} sx={{ mb: 2 }}>
            {KPI_CONFIG.map(({ key, label }) => (
              // MUI v6 Grid v1 — `item xs` is deprecated but `size` prop requires Grid2
              // TODO: migrate to Grid2 when upgrading to MUI v7
              <Grid item xs={6} key={key}>
                <KPICard
                  label={label}
                  data={kpis?.[key] ?? null}
                  loading={isLoading}
                />
              </Grid>
            ))}
          </Grid>
        )}

        {/* "Updated N min ago" / cache indicator */}
        {computedAt && (
          <Typography variant="caption" color="text.disabled" sx={{ display: 'block', mb: 2, fontSize: 10, pl: 0.5 }}>
            Updated {timeAgo(computedAt)}
          </Typography>
        )}

        <Divider sx={{ mb: 1.5 }} />

        {/* Quick Actions */}
        <Typography
          variant="caption"
          sx={{ px: 0.5, pb: 1, display: 'block', color: 'text.secondary', fontWeight: 600, letterSpacing: '0.08em' }}
        >
          QUICK ACTIONS
        </Typography>

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
          {QUICK_ACTIONS.map((action) => (
            <Button
              key={action.label}
              variant="text"
              fullWidth
              onClick={() => handleQuickAction(action.message)}
              sx={{
                justifyContent: 'flex-start',
                textAlign: 'left',
                p: 1.25,
                borderRadius: 2,
                textTransform: 'none',
                bgcolor: 'action.hover',
                '&:hover': { bgcolor: 'action.selected' },
                display: 'flex',
                alignItems: 'flex-start',
                gap: 1.25,
              }}
            >
              <Box sx={{ color: 'primary.main', mt: 0.1, flexShrink: 0 }}>
                {action.icon}
              </Box>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography variant="body2" fontWeight={500} sx={{ fontSize: 12, lineHeight: 1.3, color: 'text.primary' }}>
                  {action.label}
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: 10, display: 'block', lineHeight: 1.3 }}>
                  {action.sub}
                </Typography>
              </Box>
              <Typography color="text.disabled" sx={{ fontSize: 14, mt: 0.1, flexShrink: 0 }}>→</Typography>
            </Button>
          ))}
        </Box>
      </Box>
    </Box>
  )
}
