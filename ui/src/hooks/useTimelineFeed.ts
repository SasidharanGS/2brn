import { useState, useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { queryKeys } from '../api/queryKeys'
import type { ActivityRecord } from '../api/types'
import { useAppDate } from '../context/DateContext'

export const ALL_CATEGORIES = ['work','research','play','learning','communication','creative','admin','other'] as const
export const ALL_STATES = ['productive','focused','chilling','procrastinating','distracted','in-meeting','idle'] as const

export type TimelineCategory = typeof ALL_CATEGORIES[number]
export type TimelineState = typeof ALL_STATES[number]

/** Timeline data + filter/selection state for the selected date. */
export function useTimelineFeed() {
  const { selectedDate } = useAppDate()
  const [selected, setSelected]             = useState<ActivityRecord | null>(null)
  const [categoryFilter, setCategoryFilter] = useState<TimelineCategory | null>(null)
  const [stateFilter, setStateFilter]       = useState<TimelineState | null>(null)
  const [search, setSearch]                 = useState('')

  // Collapse expanded row + clear filters when date changes via calendar
  useEffect(() => {
    setSelected(null)
    setCategoryFilter(null)
    setStateFilter(null)
    setSearch('')
  }, [selectedDate])

  const { data: activities = [], isLoading: loadActs } = useQuery({
    queryKey: queryKeys.activities(selectedDate),
    queryFn: () => api.getActivities({ date: selectedDate }),
    select: acts => [...acts].sort((a, b) => b.started_at.localeCompare(a.started_at)),
  })
  const { data: captures = [], isLoading: loadCaps } = useQuery({
    queryKey: queryKeys.captures(selectedDate),
    queryFn: () => api.getCaptures(selectedDate),
  })
  const { data: sessions } = useQuery({
    queryKey: queryKeys.sessions(selectedDate),
    queryFn: () => api.getSessions(selectedDate),
  })
  const loading = loadActs || loadCaps

  // Apply filters
  const filtered = useMemo(() => {
    return activities.filter(a => {
      if (categoryFilter && a.task_category !== categoryFilter) return false
      if (stateFilter    && a.productivity_state !== stateFilter) return false
      if (search.trim()) {
        const q = search.trim().toLowerCase()
        if (!a.summary?.toLowerCase().includes(q)) return false
      }
      return true
    })
  }, [activities, categoryFilter, stateFilter, search])

  // Which categories/states actually appear in today's data (for dimming empty ones)
  const presentCategories = useMemo(() => new Set(activities.map(a => a.task_category)), [activities])
  const presentStates     = useMemo(() => new Set(activities.map(a => a.productivity_state)), [activities])

  const hasFilters = categoryFilter !== null || stateFilter !== null || search.trim() !== ''

  function clearFilters() {
    setCategoryFilter(null)
    setStateFilter(null)
    setSearch('')
  }

  return {
    selectedDate,
    activities, captures, sessions, loading,
    filtered, presentCategories, presentStates,
    selected, setSelected,
    categoryFilter, setCategoryFilter,
    stateFilter, setStateFilter,
    search, setSearch,
    hasFilters, clearFilters,
  }
}
