import { useEffect } from 'react'
import { Box, Card, CardContent, Grid, Typography, Skeleton, Button, Chip } from '@mui/material'
import TrendingUpIcon from '@mui/icons-material/TrendingUp'
import ChatIcon from '@mui/icons-material/Chat'
import UploadIcon from '@mui/icons-material/Upload'
import { useNavigate } from 'react-router-dom'
import { useDashboardStore } from '../stores/dashboardStore'
import { useDocumentStore } from '../stores/documentStore'
import { KPIValue } from '../types'

const KPI_CONFIG: { key: string; label: string }[] = [
  { key: 'revenue', label: 'Revenue' },
  { key: 'grossMargin', label: 'Gross Margin' },
  { key: 'ebitda', label: 'EBITDA' },
  { key: 'netIncome', label: 'Net Income' },
  { key: 'cashBalance', label: 'Cash Balance' },
  { key: 'runway', label: 'Runway' },
]

function KPICard({ label, data, loading }: { label: string; data: KPIValue | null; loading: boolean }) {
  if (loading) {
    return (
      <Card>
        <CardContent>
          <Skeleton width="40%" height={20} />
          <Skeleton width="70%" height={40} sx={{ mt: 1 }} />
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardContent>
        <Typography variant="body2" color="text.secondary">{label}</Typography>
        <Typography variant="h5" fontWeight={700} sx={{ mt: 0.5 }}>
          {data?.value ?? '—'}
        </Typography>
        {data?.change && (
          <Typography variant="caption" color={data.favorable ? 'secondary.main' : 'error.main'}>
            {data.change}
          </Typography>
        )}
      </CardContent>
    </Card>
  )
}

export default function Dashboard() {
  const navigate = useNavigate()
  const { kpis, loading, lastUpdated, fetchKPIs } = useDashboardStore()
  const { documents, fetchDocuments } = useDocumentStore()

  useEffect(() => { fetchDocuments() }, [fetchDocuments])

  useEffect(() => {
    if (documents.length > 0 && !lastUpdated) {
      fetchKPIs()
    }
  }, [documents, lastUpdated, fetchKPIs])

  const hasDocuments = documents.length > 0

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h5" fontWeight={600}>Dashboard</Typography>
          {lastUpdated && (
            <Typography variant="caption" color="text.secondary">Last updated: {lastUpdated}</Typography>
          )}
        </Box>
        {hasDocuments && (
          <Chip icon={<TrendingUpIcon />} label={`${documents.length} documents indexed`} variant="outlined" />
        )}
      </Box>

      {/* KPI Grid */}
      {hasDocuments ? (
        <Grid container spacing={2} sx={{ mb: 4 }}>
          {KPI_CONFIG.map(({ key, label }) => (
            <Grid item xs={12} sm={6} md={4} key={key}>
              <KPICard
                label={label}
                data={kpis[key as keyof typeof kpis]}
                loading={loading}
              />
            </Grid>
          ))}
        </Grid>
      ) : (
        <Card sx={{ mb: 4, textAlign: 'center', py: 6 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>No documents uploaded yet</Typography>
            <Typography color="text.secondary" sx={{ mb: 2 }}>
              Upload financial documents to populate your KPI dashboard
            </Typography>
            <Button variant="contained" startIcon={<UploadIcon />} onClick={() => navigate('/documents')}>
              Upload Documents
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Quick Actions */}
      <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>Quick Actions</Typography>
      <Box sx={{ display: 'flex', gap: 2 }}>
        <Button variant="outlined" startIcon={<ChatIcon />} onClick={() => navigate('/chat')}>
          Ask a Question
        </Button>
        <Button variant="outlined" startIcon={<UploadIcon />} onClick={() => navigate('/documents')}>
          Upload Documents
        </Button>
      </Box>
    </Box>
  )
}
