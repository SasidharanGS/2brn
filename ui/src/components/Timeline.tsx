import { useState, useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { queryKeys } from '../api/queryKeys'
import { categoryChip, stateChip } from '../utils/design'
import type { ActivityRecord, SessionsResponse } from '../api/types'
import { useAppDate } from '../context/DateContext'

const ALL_CATEGORIES = ['work','research','play','learning','communication','creative','admin','other'] as const
const ALL_STATES = ['productive','focused','chilling','procrastinating','distracted','in-meeting','idle'] as const

type Category = typeof ALL_CATEGORIES[number]
type State = typeof ALL_STATES[number]

function fmtDur(seconds: number): string {
  const m = Math.round(seconds / 60)
  if (m < 1) return '<1m'
  const h = Math.floor(m / 60)
  const rem = m % 60
  if (h === 0) return `${m}m`
  return rem === 0 ? `${h}h` : `${h}h ${rem}m`
}

const fmtClock = (ts: number | string) =>
  new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

/** Per-monitor lanes of duration blocks, plus clock-time totals by category. */
function SessionLanes({ sessions }: { sessions: SessionsResponse }) {
  const { blocks, totals } = sessions
  if (blocks.length === 0) return null

  const t0 = Math.min(...blocks.map(b => Date.parse(b.start)))
  const t1 = Math.max(...blocks.map(b => Date.parse(b.end)))
  const span = Math.max(t1 - t0, 1)
  const monitors = [...new Set(blocks.map(b => b.monitor_index))].sort((a, b) => a - b)
  const catTotals = Object.entries(totals.by_category).sort((a, b) => b[1] - a[1])

  return (
    <div
      className="rounded-[12px] border p-4 mb-5"
      style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-[10px] uppercase tracking-widest font-medium" style={{ color: 'var(--text-dim)' }}>
          Blocks
        </span>
        <span className="text-[11px] font-mono" style={{ color: 'var(--text-dim)' }}>
          {fmtDur(totals.observed_seconds)} on screen
        </span>
      </div>

      <div className="space-y-1.5">
        {monitors.map(m => (
          <div key={m} className="flex items-center gap-2">
            {monitors.length > 1 && (
              <span className="text-[10px] font-mono w-6 shrink-0 text-right" style={{ color: 'var(--text-dim)' }}>
                M{m}
              </span>
            )}
            <div className="relative h-6 flex-1 rounded-[6px] overflow-hidden" style={{ background: 'var(--bg-surface-2)' }}>
              {blocks.filter(b => b.monitor_index === m).map((b, i) => {
                const chip = categoryChip(b.task_category)
                const left = ((Date.parse(b.start) - t0) / span) * 100
                const width = Math.max(((Date.parse(b.end) - Date.parse(b.start)) / span) * 100, 0.35)
                const tip = [
                  `${b.app_name ?? 'unknown'} · ${b.task_category ?? 'other'} · ${fmtDur(b.duration_seconds)}`,
                  `${fmtClock(b.start)}–${fmtClock(b.end)}`,
                  b.summary ?? '',
                ].filter(Boolean).join('\n')
                return (
                  <div
                    key={i}
                    className="absolute top-0 h-full"
                    title={tip}
                    style={{ left: `${left}%`, width: `${width}%`, background: chip.dot, opacity: 0.85 }}
                  />
                )
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="flex justify-between mt-1.5 text-[10px] font-mono" style={{ color: 'var(--text-dim)' }}>
        <span>{fmtClock(t0)}</span>
        <span>{fmtClock(t1)}</span>
      </div>

      <div className="flex flex-wrap gap-1.5 mt-3">
        {catTotals.map(([cat, secs]) => {
          const chip = categoryChip(cat)
          return (
            <span
              key={cat}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium"
              style={{ background: chip.bg, color: chip.text }}
            >
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: chip.dot }} />
              {cat} {fmtDur(secs)}
            </span>
          )
        })}
      </div>
    </div>
  )
}

export default function Timeline() {
  const { selectedDate } = useAppDate()
  const [selected, setSelected]               = useState<ActivityRecord | null>(null)
  const [categoryFilter, setCategoryFilter]   = useState<Category | null>(null)
  const [stateFilter, setStateFilter]         = useState<State | null>(null)
  const [search, setSearch]                   = useState('')

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

  return (
    <div className="page-enter p-7">

      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-[19px] font-semibold tracking-tight" style={{ color: 'var(--text)' }}>
            Timeline
          </h1>
          <p className="text-[12px] mt-0.5 font-mono" style={{ color: 'var(--text-dim)' }}>
            {hasFilters
              ? <>{filtered.length} <span style={{ color: 'var(--text-dim)' }}>of</span> {activities.length} activities · {captures.length} captures</>
              : <>{captures.length} captures · {activities.length} activities</>
            }
          </p>
        </div>
        {hasFilters && (
          <button
            onClick={clearFilters}
            className="text-[12px] px-3 py-1.5 rounded-[7px] transition-all"
            style={{ color: 'var(--text-dim)', background: 'var(--bg-surface-2)', border: '1px solid var(--border)' }}
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Duration blocks (per-monitor lanes + clock-time totals) */}
      {!loading && sessions && <SessionLanes sessions={sessions} />}

      {/* Filter bar */}
      {!loading && activities.length > 0 && (
        <div
          className="rounded-[12px] border p-3 mb-5 space-y-2.5"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
        >
          {/* Search */}
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search activities…"
            className="w-full rounded-[8px] border px-3 py-1.5 text-[13px] outline-none"
            style={{
              background: 'var(--bg-input)',
              borderColor: search ? 'var(--accent)' : 'var(--border-2)',
              color: 'var(--text)',
            }}
          />

          {/* Category pills */}
          <div className="flex flex-wrap gap-1.5">
            <span className="text-[10px] uppercase tracking-widest self-center mr-1 font-medium" style={{ color: 'var(--text-dim)' }}>
              Category
            </span>
            {ALL_CATEGORIES.map(cat => {
              const chip = categoryChip(cat)
              const active = categoryFilter === cat
              const present = presentCategories.has(cat)
              return (
                <button
                  key={cat}
                  onClick={() => setCategoryFilter(active ? null : cat)}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium transition-all duration-100"
                  style={{
                    background: active ? chip.bg : 'var(--bg-surface-2)',
                    color: active ? chip.text : present ? 'var(--text-muted)' : 'var(--text-dim)',
                    border: active ? `1px solid ${chip.text}40` : '1px solid var(--border)',
                    opacity: present ? 1 : 0.4,
                  }}
                  disabled={!present}
                >
                  <span className="w-1.5 h-1.5 rounded-full" style={{ background: chip.dot }} />
                  {cat}
                </button>
              )
            })}
          </div>

          {/* State pills */}
          <div className="flex flex-wrap gap-1.5">
            <span className="text-[10px] uppercase tracking-widest self-center mr-1 font-medium" style={{ color: 'var(--text-dim)' }}>
              State
            </span>
            {ALL_STATES.map(state => {
              const chip = stateChip(state)
              const active = stateFilter === state
              const present = presentStates.has(state)
              const label = state === 'in-meeting' ? 'meeting' : state
              return (
                <button
                  key={state}
                  onClick={() => setStateFilter(active ? null : state)}
                  className="px-2.5 py-1 rounded-full text-[11px] font-medium transition-all duration-100"
                  style={{
                    background: active ? chip.bg : 'var(--bg-surface-2)',
                    color: active ? chip.text : present ? 'var(--text-muted)' : 'var(--text-dim)',
                    border: active ? `1px solid ${chip.text}40` : '1px solid var(--border)',
                    opacity: present ? 1 : 0.4,
                  }}
                  disabled={!present}
                >
                  {label}
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* Skeleton */}
      {loading ? (
        <div className="space-y-2">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="skeleton h-14 rounded-[10px]" style={{ opacity: 1 - i * 0.12 }} />
          ))}
        </div>

      ) : activities.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <div className="text-4xl mb-4 opacity-20">⏱</div>
          <div className="text-[14px]" style={{ color: 'var(--text-muted)' }}>
            No activity recorded for {selectedDate}
          </div>
        </div>

      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="text-3xl mb-3 opacity-20">◎</div>
          <div className="text-[14px] mb-3" style={{ color: 'var(--text-muted)' }}>
            No activities match the current filters
          </div>
          <button
            onClick={clearFilters}
            className="text-[12px] px-3 py-1.5 rounded-[7px] transition-all"
            style={{ color: 'var(--accent)', background: 'var(--accent-glow)', border: '1px solid rgba(129,140,248,0.2)' }}
          >
            Clear filters
          </button>
        </div>

      ) : (
        <div className="space-y-1.5">
          {filtered.map(act => {
            const cc = categoryChip(act.task_category)
            const sc = stateChip(act.productivity_state)
            const isSelected = selected?.id === act.id
            return (
              <button
                key={act.id}
                onClick={() => setSelected(isSelected ? null : act)}
                className="w-full text-left rounded-[10px] border px-4 py-3 transition-all duration-150"
                style={{
                  background: isSelected ? 'var(--bg-surface-2)' : 'var(--bg-surface)',
                  borderColor: isSelected ? 'rgba(129,140,248,0.4)' : 'var(--border)',
                  boxShadow: isSelected ? '0 0 0 1px rgba(129,140,248,0.2)' : 'none',
                }}
              >
                <div className="flex items-center gap-3">
                  <span className="w-2 h-2 rounded-full shrink-0" style={{ background: cc.dot }} />
                  <span className="text-[11px] font-mono w-10 shrink-0 tabular-nums" style={{ color: 'var(--text-dim)' }}>
                    {new Date(act.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                  <span className="text-[14px] flex-1 truncate" style={{ color: 'var(--text)' }}>
                    {act.summary ?? '—'}
                  </span>
                  <span
                    className="text-[11px] px-2 py-0.5 rounded-full font-medium shrink-0"
                    style={{ background: cc.bg, color: cc.text }}
                  >
                    {act.task_category ?? 'other'}
                  </span>
                  <span
                    className="text-[11px] px-2 py-0.5 rounded-full shrink-0 hidden sm:block"
                    style={{ background: sc.bg, color: sc.text }}
                  >
                    {act.productivity_state ?? '—'}
                  </span>
                </div>

                {isSelected && act.summary && (
                  <div
                    className="mt-3 pt-3 border-t text-[13px] leading-relaxed"
                    style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}
                  >
                    {act.summary}
                  </div>
                )}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
