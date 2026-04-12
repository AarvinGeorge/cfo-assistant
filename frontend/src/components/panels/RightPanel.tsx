import { useEffect } from 'react'
import {
  Box, Typography, IconButton, Tooltip, Grid, Skeleton,
  Card, CardContent, Button, Divider,
} from '@mui/material'
import RefreshIcon from '@mui/icons-material/Refresh'
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft'
import ChevronRightIcon from '@mui/icons-material/ChevronRight'
import TrendingUpIcon from '@mui/icons-material/TrendingUp'
import TrendingDownIcon from '@mui/icons-material/TrendingDown'
import ShowChartIcon from '@mui/icons-material/ShowChart'
import ScatterPlotIcon from '@mui/icons-material/ScatterPlot'
import TimelineIcon from '@mui/icons-material/Timeline'
import DownloadIcon from '@mui/icons-material/Download'
import DashboardIcon from '@mui/icons-material/Dashboard'
import { useDashboardStore } from '../../stores/dashboardStore'
import { useDocumentStore } from '../../stores/documentStore'
import { useSessionStore } from '../../stores/sessionStore'
import { useChatStore } from '../../stores/chatStore'
import { KPIValue } from '../../types'

const KPI_CONFIG: { key: string; label: string }[] = [
  { key: 'revenue', label: 'Revenue' },
  { key: 'grossMargin', label: 'Gross Margin' },
  { key: 'ebitda', label: 'EBITDA' },
  { key: 'netIncome', label: 'Net Income' },
  { key: 'cashBalance', label: 'Cash Balance' },
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

function KPICard({ label, data, loading }: { label: string; data: KPIValue | null; loading: boolean }) {
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

  return (
    <Card variant="outlined" sx={{ bgcolor: 'action.hover', border: 'none' }}>
      <CardContent sx={{ p: '10px !important' }}>
        <Typography variant="caption" color="text.secondary" sx={{ fontSize: 10, fontWeight: 500, letterSpacing: '0.04em' }}>
          {label.toUpperCase()}
        </Typography>
        <Typography variant="body1" fontWeight={700} sx={{ lineHeight: 1.3, mt: 0.25 }}>
          {data?.value ?? '—'}
        </Typography>
        {data?.change && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25, mt: 0.25 }}>
            {data.favorable
              ? <TrendingUpIcon sx={{ fontSize: 11, color: 'secondary.main' }} />
              : <TrendingDownIcon sx={{ fontSize: 11, color: 'error.main' }} />
            }
            <Typography
              variant="caption"
              sx={{ fontSize: 10, color: data.favorable ? 'secondary.main' : 'error.main', fontWeight: 500 }}
            >
              {data.change}
            </Typography>
          </Box>
        )}
      </CardContent>
    </Card>
  )
}

export default function RightPanel() {
  const { kpis, loading, lastUpdated, fetchKPIs } = useDashboardStore()
  const { documents } = useDocumentStore()
  const { rightPanelOpen, toggleRightPanel } = useSessionStore()
  const { sendMessage } = useChatStore()

  useEffect(() => {
    if (documents.length > 0 && !lastUpdated) {
      fetchKPIs()
    }
  }, [documents, lastUpdated, fetchKPIs])

  const handleQuickAction = (message: string) => {
    sendMessage(message)
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
            <IconButton size="small" onClick={fetchKPIs} disabled={loading || documents.length === 0}>
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

        {documents.length === 0 && !loading ? (
          <Box sx={{ textAlign: 'center', py: 3, px: 1 }}>
            <Typography variant="body2" color="text.secondary" sx={{ fontSize: 12 }}>
              Upload documents to populate KPIs
            </Typography>
          </Box>
        ) : (
          <Grid container spacing={1} sx={{ mb: 2 }}>
            {KPI_CONFIG.map(({ key, label }) => (
              // MUI v6 Grid v1 — `item xs` is deprecated but `size` prop requires Grid2
              // TODO: migrate to Grid2 when upgrading to MUI v7
              <Grid item xs={6} key={key}>
                <KPICard
                  label={label}
                  data={kpis[key as keyof typeof kpis]}
                  loading={loading}
                />
              </Grid>
            ))}
          </Grid>
        )}

        {lastUpdated && (
          <Typography variant="caption" color="text.disabled" sx={{ display: 'block', mb: 2, fontSize: 10, pl: 0.5 }}>
            Updated {lastUpdated}
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
