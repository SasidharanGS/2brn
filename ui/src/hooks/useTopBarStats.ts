import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { queryKeys } from '../api/queryKeys'
import { toDateStr } from '../context/DateContext'

/** Live top-bar stats for today: top state/category, observed time, focus %. */
export function useTopBarStats() {
  const today = toDateStr(new Date())
  const { data: insights } = useQuery({
    queryKey: queryKeys.insightsSummary(today, 'day'),
    queryFn: () => api.getInsightsSummary(today, 'day'),
    refetchInterval: 30_000,
  })

  // All time-based: buckets arrive sorted by block-time; focus% is the
  // productive share of observed time.
  return {
    topState:    insights?.productivity_states[0]?.productivity_state ?? null,
    topCategory: insights?.categories[0]?.task_category ?? null,
    observed:    insights?.observed_seconds ?? 0,
    focusPct:    Math.round(insights?.comparison.productive.current_pct ?? 0),
  }
}
