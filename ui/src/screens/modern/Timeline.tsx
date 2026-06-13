import { useEffect, useMemo, useRef, useState } from 'react'
import { categoryChip, stateChip } from '../../utils/design'
import { fmtDur } from '../../utils/time'
import type { ActivityRecord, SessionsResponse } from '../../api/types'
import { useTimelineFeed, ALL_CATEGORIES, ALL_STATES } from '../../hooks/useTimelineFeed'
import { groupActivitiesByHour } from '../../utils/timeline'

const fmtClock = (ts: number | string) =>
  new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

/** Whole-hour label for the rail + sticky headings, e.g. "09:00 am". */
function fmtHour(h: number): string {
  const ap = h < 12 ? 'am' : 'pm'
  const hh = h % 12 === 0 ? 12 : h % 12
  return `${String(hh).padStart(2, '0')}:00 ${ap}`
}

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

/** One clickable hour line in the rail. Length encodes activity count; the line
    turns accent + reveals the time on hover, and stays accent while its hour is
    the active (scroll-spied) section. Mirrors the minimal skin's interaction. */
function HourTick({ hour, has, count, isActive, isHover, onClick, onEnter, onLeave }: {
  hour: number; has: boolean; count: number
  isActive: boolean; isHover: boolean; onClick: () => void; onEnter: () => void; onLeave: () => void
}) {
  const lit = isActive || isHover
  const lineColor = lit ? 'var(--accent)' : has ? 'var(--text-muted)' : 'var(--border)'
  const lineW = isHover ? 44 : has ? Math.min(16 + count * 6, 34) : 12
  return (
    <button
      type="button" onClick={onClick} onMouseEnter={onEnter} onMouseLeave={onLeave} title={fmtHour(hour)}
      className="flex items-center gap-2.5"
      style={{ height: 26, width: '100%', background: 'none', border: 'none', padding: 0, cursor: 'pointer' }}
    >
      <span
        aria-hidden="true"
        style={{
          height: lit || has ? 2 : 1, width: lineW, background: lineColor, flexShrink: 0, borderRadius: 1,
          transition: 'width 0.18s ease, background 0.18s ease, height 0.18s ease',
        }}
      />
      <span
        className="font-mono"
        style={{
          fontSize: 10, letterSpacing: '0.05em', whiteSpace: 'nowrap', pointerEvents: 'none',
          color: isActive ? 'var(--text)' : 'var(--text-dim)', opacity: lit ? 1 : 0, transition: 'opacity 0.18s ease',
        }}
      >
        {fmtHour(hour)}
      </span>
    </button>
  )
}

/** One activity row card (selectable, expands to show its summary). */
function ActivityRow({ act, selected, onToggle }: {
  act: ActivityRecord; selected: boolean; onToggle: () => void
}) {
  const cc = categoryChip(act.task_category)
  const sc = stateChip(act.productivity_state)
  return (
    <button
      onClick={onToggle}
      className="w-full text-left rounded-[10px] border px-4 py-3 transition-all duration-150"
      style={{
        background: selected ? 'var(--bg-surface-2)' : 'var(--bg-surface)',
        borderColor: selected ? 'rgba(129,140,248,0.4)' : 'var(--border)',
        boxShadow: selected ? '0 0 0 1px rgba(129,140,248,0.2)' : 'none',
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

      {selected && act.summary && (
        <div
          className="mt-3 pt-3 border-t text-[13px] leading-relaxed"
          style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}
        >
          {act.summary}
        </div>
      )}
    </button>
  )
}

export default function Timeline() {
  const {
    selectedDate, activities, captures, sessions, loading,
    filtered, presentCategories, presentStates,
    selected, setSelected,
    categoryFilter, setCategoryFilter,
    stateFilter, setStateFilter,
    search, setSearch,
    hasFilters, clearFilters,
  } = useTimelineFeed()

  const [activeHour, setActiveHour] = useState<number | null>(null)
  const [hoverHour, setHoverHour]   = useState<number | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const hourRefs  = useRef<Record<number, HTMLElement | null>>({})

  // Group the filtered feed by hour, newest-first, via the shared util so both
  // skins render in identical order (latest entry on top).
  const { byHour, activeHours, railHours } = useMemo(() => groupActivitiesByHour(filtered), [filtered])

  const goToHour = (h: number) => {
    let target = h
    if (!byHour.has(h) && activeHours.length) {
      target = activeHours.reduce((best, cur) => (Math.abs(cur - h) < Math.abs(best - h) ? cur : best), activeHours[0])
    }
    const el = hourRefs.current[target]
    const sc = scrollRef.current
    if (el && sc) sc.scrollTo({ top: el.offsetTop - 8, behavior: 'smooth' })
    setActiveHour(target)
  }

  // Scroll-spy: highlight the hour section whose heading is at the top of the feed
  // (the bottom-most section whose top has scrolled past), independent of ordering.
  useEffect(() => {
    const sc = scrollRef.current
    if (!sc) return
    const onScroll = () => {
      let cur: number | null = activeHours[0] ?? null
      let bestTop = -Infinity
      for (const h of activeHours) {
        const el = hourRefs.current[h]
        if (el && el.offsetTop - 20 <= sc.scrollTop && el.offsetTop > bestTop) {
          bestTop = el.offsetTop
          cur = h
        }
      }
      setActiveHour(cur)
    }
    onScroll()
    sc.addEventListener('scroll', onScroll, { passive: true })
    return () => sc.removeEventListener('scroll', onScroll)
  }, [filtered]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex flex-col h-full p-7">

      {/* Header (non-scrolling) */}
      <div className="shrink-0">
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

        {/* Duration blocks (per-monitor lanes + clock-time category totals) */}
        {!loading && sessions && <SessionLanes sessions={sessions} />}

        {/* Filter bar */}
        {!loading && activities.length > 0 && (
          <div
            className="rounded-[12px] border p-3 mb-5 space-y-2.5"
            style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
          >
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
      </div>

      {/* Feed */}
      {loading ? (
        <div className="flex-1 min-h-0 overflow-auto space-y-2">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="skeleton h-14 rounded-[10px]" style={{ opacity: 1 - i * 0.12 }} />
          ))}
        </div>

      ) : activities.length === 0 ? (
        <div className="flex-1 min-h-0 flex flex-col items-center justify-center text-center">
          <div className="text-4xl mb-4 opacity-20">⏱</div>
          <div className="text-[14px]" style={{ color: 'var(--text-muted)' }}>
            No activity recorded for {selectedDate}
          </div>
        </div>

      ) : filtered.length === 0 ? (
        <div className="flex-1 min-h-0 flex flex-col items-center justify-center text-center">
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
        <div className="flex-1 min-h-0 flex gap-5">
          {/* Clickable hour rail */}
          <div
            className="shrink-0 flex flex-col gap-0.5 pt-2 pr-3 overflow-y-auto border-r"
            style={{ borderColor: 'var(--border)' }}
          >
            {railHours.map(h => (
              <HourTick
                key={h} hour={h} has={byHour.has(h)} count={byHour.get(h)?.length ?? 0}
                isActive={activeHour === h} isHover={hoverHour === h}
                onClick={() => goToHour(h)}
                onEnter={() => setHoverHour(h)} onLeave={() => setHoverHour(null)}
              />
            ))}
          </div>

          {/* Scrollable feed grouped by hour (newest-first) */}
          <div ref={scrollRef} className="flex-1 min-h-0 overflow-y-auto pr-1 pb-2">
            {activeHours.map(h => (
              <section key={h} ref={el => { hourRefs.current[h] = el }} className="mb-3">
                <div
                  className="sticky top-0 z-[1] flex items-center gap-2 py-1.5"
                  style={{ background: 'var(--bg-base)' }}
                >
                  <span
                    className="font-mono text-[10px] tracking-wider"
                    style={{ color: activeHour === h ? 'var(--accent)' : 'var(--text-dim)', transition: 'color 0.2s ease' }}
                  >
                    {fmtHour(h)}
                  </span>
                  <span
                    className="flex-1 h-px"
                    style={{ background: activeHour === h ? 'var(--accent)' : 'var(--border)', transition: 'background 0.2s ease' }}
                  />
                </div>
                <div className="space-y-1.5 pt-1.5">
                  {byHour.get(h)!.map(act => (
                    <ActivityRow
                      key={act.id}
                      act={act}
                      selected={selected?.id === act.id}
                      onToggle={() => setSelected(selected?.id === act.id ? null : act)}
                    />
                  ))}
                </div>
              </section>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
