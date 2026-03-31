import { create } from 'zustand'
import axiosClient from '../api/axiosClient'
import { KPIValue } from '../types'

interface KPIs {
  revenue: KPIValue | null
  grossMargin: KPIValue | null
  ebitda: KPIValue | null
  netIncome: KPIValue | null
  cashBalance: KPIValue | null
  runway: KPIValue | null
}

interface DashboardState {
  kpis: KPIs
  loading: boolean
  lastUpdated: string | null
  fetchKPIs: () => Promise<void>
}

const KPI_QUERIES: { key: keyof KPIs; query: string; format: 'currency' | 'percent' | 'months' }[] = [
  { key: 'revenue', query: 'What is the latest total revenue? Reply with just the number.', format: 'currency' },
  { key: 'grossMargin', query: 'What is the current gross margin percentage? Reply with just the percentage.', format: 'percent' },
  { key: 'ebitda', query: 'What is the latest EBITDA? Reply with just the number.', format: 'currency' },
  { key: 'netIncome', query: 'What is the latest net income? Reply with just the number.', format: 'currency' },
  { key: 'cashBalance', query: 'What is the current cash balance? Reply with just the number.', format: 'currency' },
  { key: 'runway', query: 'What is the estimated cash runway in months? Reply with just the number.', format: 'months' },
]

function parseKPIResponse(text: string, format: string): KPIValue | null {
  const match = text.match(/[\$]?([\d,]+\.?\d*)\s*(%|months?|M|B|K)?/i)
  if (!match) return null

  const rawStr = match[1].replace(/,/g, '')
  const rawValue = parseFloat(rawStr)
  if (isNaN(rawValue)) return null

  let value: string

  if (format === 'currency') {
    if (rawValue >= 1_000_000_000) value = `$${(rawValue / 1_000_000_000).toFixed(1)}B`
    else if (rawValue >= 1_000_000) value = `$${(rawValue / 1_000_000).toFixed(1)}M`
    else if (rawValue >= 1_000) value = `$${(rawValue / 1_000).toFixed(0)}K`
    else value = `$${rawValue.toFixed(0)}`
  } else if (format === 'percent') {
    value = rawValue > 1 ? `${rawValue.toFixed(1)}%` : `${(rawValue * 100).toFixed(1)}%`
  } else {
    value = `${rawValue.toFixed(0)} months`
  }

  return { value, rawValue }
}

export const useDashboardStore = create<DashboardState>((set) => ({
  kpis: { revenue: null, grossMargin: null, ebitda: null, netIncome: null, cashBalance: null, runway: null },
  loading: false,
  lastUpdated: null,

  fetchKPIs: async () => {
    set({ loading: true })

    const results = await Promise.allSettled(
      KPI_QUERIES.map(async ({ key, query, format }) => {
        const res = await axiosClient.post('/chat/', {
          message: query,
          session_id: 'dashboard-kpi-session',
        })
        const parsed = parseKPIResponse(res.data.response, format)
        return { key, value: parsed }
      })
    )

    const kpis: KPIs = { revenue: null, grossMargin: null, ebitda: null, netIncome: null, cashBalance: null, runway: null }
    for (const result of results) {
      if (result.status === 'fulfilled' && result.value.value) {
        kpis[result.value.key] = result.value.value
      }
    }

    set({ kpis, loading: false, lastUpdated: new Date().toLocaleString() })
  },
}))
