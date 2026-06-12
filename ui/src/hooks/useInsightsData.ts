import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { queryKeys } from '../api/queryKeys'
import { useAppDate } from '../context/DateContext'
import type { InsightsPeriod } from '../api/types'

export function fmtPct(p: number): string {
  return `${p.toFixed(1)}%`
}

/** Relative change of current vs baseline in whole percent; null when baseline is empty but current isn't. */
export function deltaPct(current: number, baseline: number): number | null {
  if (baseline <= 0) return current > 0 ? null : 0
  return Math.round(((current - baseline) / baseline) * 100)
}

/** Insights summary for the selected date + day/week/month period state. */
export function useInsightsData() {
  const { selectedDate } = useAppDate()
  const [period, setPeriod] = useState<InsightsPeriod>('day')

  const { data: summary, isLoading, isError } = useQuery({
    queryKey: queryKeys.insightsSummary(selectedDate, period),
    queryFn: () => api.getInsightsSummary(selectedDate, period),
  })

  return { selectedDate, period, setPeriod, summary, isLoading, isError }
}
