import { useEffect, useMemo, useRef, useState } from 'react'
import type { ActivityRecord } from '../../api/types'
import { useTimelineFeed, ALL_CATEGORIES, ALL_STATES } from '../../hooks/useTimelineFeed'
import { stateInk, inkVar } from './minimalDesign'
import PageHeader from './PageHeader'
import Icon from './Icon'
import { Label, Pill, StateLabel, GhostButton, EmptyState } from './primitives'

// State is encoded by intensity (the row dot + state label); category is neutral.
// The signature interaction is the clickable hour rail (left): each tick is one
// hour; click scroll-jumps the feed to that hour, hover reveals the time, and a
// scroll-spy highlights the hour currently at the top of the feed.

function FilterPill({ label, active, present, dot, level, onClick }: {
  label: string; active: boolean; present: boolean; dot?: boolean; level?: number; onClick: () => void
}) {
  return (
    <button
      type="button" onClick={onClick} disabled={!present}
      className={active ? undefined : 'm-pill-btn'}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        background: active ? 'var(--fg)' : 'none',
        color: active ? 'var(--bg)' : undefined,
        border: active ? '1px solid var(--fg)' : undefined,
        borderRadius: 'var(--radius-pill)', padding: '3px 10px',
        cursor: present ? 'pointer' : 'default',
        fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-snug)',
        fontWeight: 300, fontFamily: 'var(--font-sans)',
        opacity: present ? 1 : 0.4,
      }}
    >
      {dot && (
        <span style={{
          width: 6, height: 6, flex: '0 0 auto',
          background: active ? 'var(--bg)' : inkVar(level ?? 0),
        }} />
      )}
      {label}
    </button>
  )
}

/** Whole-hour label in the rail + sticky headings, e.g. "09:00 am" (mono). */
function fmtHour(h: number): string {
  const ap = h < 12 ? 'am' : 'pm'
  const hh = h % 12 === 0 ? 12 : h % 12
  return `${String(hh).padStart(2, '0')}:00 ${ap}`
}

function fmtRowTime(iso: string): { time: string; ampm: string } {
  const parts = new Date(iso)
    .toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
    .toLowerCase()
    .split(' ')
  return { time: parts[0] ?? '', ampm: parts[1] ?? '' }
}

/** One clickable hour line in the rail. Length/intensity encode activity; hover
    extends it + turns it accent and reveals the time. */
function HourTick({ hour, has, level, count, isActive, isHover, onClick, onEnter, onLeave }: {
  hour: number; has: boolean; level: number; count: number
  isActive: boolean; isHover: boolean; onClick: () => void; onEnter: () => void; onLeave: () => void
}) {
  const lit = isActive || isHover
  const lineColor = lit ? 'var(--accent)' : has ? inkVar(level) : 'var(--rule)'
  const lineW = isHover ? 44 : has ? Math.min(16 + count * 6, 34) : 12
  return (
    <button
      type="button" onClick={onClick} onMouseEnter={onEnter} onMouseLeave={onLeave} title={fmtHour(hour)}
      style={{
        display: 'flex', alignItems: 'center', gap: 10, height: 26, width: '100%',
        background: 'none', border: 'none', padding: 0, cursor: 'pointer',
      }}
    >
      <span aria-hidden="true" style={{
        height: lit || has ? 2 : 1, width: lineW, background: lineColor, flex: '0 0 auto',
        transition: 'width 0.18s ease, background 0.18s ease, height 0.18s ease',
      }} />
      <span style={{
        fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-wide)',
        color: isActive ? 'var(--fg)' : 'var(--muted)', opacity: lit ? 1 : 0,
        transition: 'opacity 0.18s ease', whiteSpace: 'nowrap',
        fontFamily: 'var(--font-mono)', pointerEvents: 'none',
      }}>
        {fmtHour(hour)}
      </span>
    </button>
  )
}

function ActivityRow({ act, selected, onToggle }: {
  act: ActivityRecord; selected: boolean; onToggle: () => void
}) {
  const lvl = stateInk(act.productivity_state)
  const { time, ampm } = fmtRowTime(act.started_at)
  return (
    <div
      role="button" tabIndex={0}
      onClick={onToggle}
      onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') onToggle() }}
      style={{
        display: 'grid', gridTemplateColumns: '68px 12px 1fr auto',
        gap: 'var(--space-md)', alignItems: 'center',
        borderTop: '1px solid var(--rule)', padding: 'var(--space-sm) 0', cursor: 'pointer',
      }}
    >
      <div style={{
        fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-snug)',
        color: 'var(--muted)', fontWeight: 300, whiteSpace: 'nowrap', fontFamily: 'var(--font-mono)',
      }}>
        {time} <span style={{ opacity: 0.7 }}>{ampm}</span>
      </div>
      <span style={{ width: 8, height: 8, borderRadius: '50%', background: inkVar(lvl), justifySelf: 'center' }} />
      <div style={{
        fontSize: 'var(--text-md)', color: 'var(--fg)', fontWeight: 400,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: selected ? 'normal' : 'nowrap',
      }}>
        {act.summary ?? '—'}
      </div>
      <div style={{ display: 'flex', gap: 'var(--space-xs)', alignItems: 'center' }}>
        <Pill>{act.task_category ?? 'other'}</Pill>
        <StateLabel state={act.productivity_state ?? '—'} level={lvl} />
      </div>
    </div>
  )
}

export default function Timeline() {
  const {
    selectedDate, activities, captures, loading,
    filtered, presentCategories, presentStates,
    selected, setSelected,
    categoryFilter, setCategoryFilter,
    stateFilter, setStateFilter,
    search, setSearch,
    hasFilters, clearFilters,
  } = useTimelineFeed()

  const [activeHour, setActiveHour] = useState<number | null>(null)
  const [hoverHour, setHoverHour] = useState<number | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const hourRefs = useRef<Record<number, HTMLElement | null>>({})

  // Group the filtered feed by local hour, ascending (chronological). The shared
  // hook sorts newest-first; the timeline reads top-to-bottom morning→evening, so
  // we re-sort locally without touching the hook (modern timeline is unaffected).
  const { byHour, activeHours, railHours } = useMemo(() => {
    const m = new Map<number, ActivityRecord[]>()
    for (const a of filtered) {
      const h = new Date(a.started_at).getHours()
      const bucket = m.get(h)
      if (bucket) bucket.push(a)
      else m.set(h, [a])
    }
    for (const bucket of m.values()) bucket.sort((a, b) => a.started_at.localeCompare(b.started_at))
    const hours = [...m.keys()].sort((x, y) => x - y)
    const rail: number[] = []
    if (hours.length) for (let h = hours[0]; h <= hours[hours.length - 1]; h++) rail.push(h)
    return { byHour: m, activeHours: hours, railHours: rail }
  }, [filtered])

  const hourLevel = (h: number) => {
    const bucket = byHour.get(h)
    return bucket ? Math.max(...bucket.map(a => stateInk(a.productivity_state))) : 0
  }

  const goToHour = (h: number) => {
    let target = h
    if (!byHour.has(h)) {
      const after = activeHours.filter(x => x >= h)
      target = after.length ? after[0] : activeHours[activeHours.length - 1]
    }
    const el = hourRefs.current[target]
    const sc = scrollRef.current
    // Scroll the feed container by offset — never scrollIntoView (it shifts the
    // whole app layout).
    if (el && sc) sc.scrollTo({ top: el.offsetTop - 8, behavior: 'smooth' })
    setActiveHour(target)
  }

  // Scroll-spy: highlight the hour group currently at the top of the feed.
  useEffect(() => {
    const sc = scrollRef.current
    if (!sc) return
    const onScroll = () => {
      let cur: number | null = activeHours[0] ?? null
      for (const h of activeHours) {
        const el = hourRefs.current[h]
        if (el && el.offsetTop - 20 <= sc.scrollTop) cur = h
      }
      setActiveHour(cur)
    }
    onScroll()
    sc.addEventListener('scroll', onScroll, { passive: true })
    return () => sc.removeEventListener('scroll', onScroll)
  }, [filtered]) // eslint-disable-line react-hooks/exhaustive-deps

  const subtitle = hasFilters
    ? `${filtered.length} of ${activities.length} activities · ${captures.length} captures`
    : `${captures.length} captures · ${activities.length} activities`

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%',
      padding: 'var(--space-lg)', boxSizing: 'border-box',
    }}>
      <div style={{ flex: '0 0 auto' }}>
        <PageHeader
          title="timeline"
          subtitle={subtitle}
          right={hasFilters ? <GhostButton onClick={clearFilters}>clear filters</GhostButton> : undefined}
        />

        {!loading && activities.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)', marginBottom: 'var(--space-lg)' }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 'var(--space-sm)',
              border: '1px solid var(--rule)', padding: 'var(--space-sm) var(--space-md)',
            }}>
              <span style={{ color: 'var(--muted)' }}><Icon name="search" size={15} /></span>
              <input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="search activities…"
                style={{
                  flex: 1, background: 'none', border: 'none', outline: 'none',
                  color: 'var(--fg)', fontSize: 'var(--text-base)', fontWeight: 300,
                  fontFamily: 'var(--font-sans)',
                }}
              />
            </div>

            <div style={{
              display: 'grid', gridTemplateColumns: 'auto 1fr',
              gap: 'var(--space-sm) var(--space-md)', alignItems: 'center',
            }}>
              <Label>category</Label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-xs)' }}>
                {ALL_CATEGORIES.map(c => (
                  <FilterPill
                    key={c} label={c}
                    active={categoryFilter === c}
                    present={presentCategories.has(c)}
                    onClick={() => setCategoryFilter(categoryFilter === c ? null : c)}
                  />
                ))}
              </div>
              <Label>state</Label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-xs)' }}>
                {ALL_STATES.map(s => (
                  <FilterPill
                    key={s} label={s === 'in-meeting' ? 'meeting' : s}
                    dot level={stateInk(s)}
                    active={stateFilter === s}
                    present={presentStates.has(s)}
                    onClick={() => setStateFilter(stateFilter === s ? null : s)}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Feed */}
      {loading ? (
        <div style={{ fontSize: 'var(--text-base)', color: 'var(--muted)', fontWeight: 300 }}>loading…</div>

      ) : activities.length === 0 ? (
        <EmptyState icon={<Icon name="timeline" size={28} strokeWidth={1.2} />} title={`no activity recorded for ${selectedDate}`} />

      ) : filtered.length === 0 ? (
        <EmptyState dashed title="no activities match the current filters">
          <GhostButton onClick={clearFilters}>clear filters</GhostButton>
        </EmptyState>

      ) : (
        <div style={{ flex: 1, minHeight: 0, display: 'flex', gap: 'var(--space-lg)' }}>
          {/* Clickable hour rail */}
          <div style={{
            flex: '0 0 auto', display: 'flex', flexDirection: 'column', gap: 2,
            paddingTop: 'var(--space-sm)', paddingRight: 'var(--space-md)',
            borderRight: '1px solid var(--rule)', overflowY: 'auto',
          }}>
            {railHours.map(h => (
              <HourTick
                key={h} hour={h} has={byHour.has(h)} level={hourLevel(h)}
                count={byHour.get(h)?.length ?? 0}
                isActive={activeHour === h} isHover={hoverHour === h}
                onClick={() => goToHour(h)}
                onEnter={() => setHoverHour(h)} onLeave={() => setHoverHour(null)}
              />
            ))}
          </div>

          {/* Scrollable feed grouped by hour */}
          <div ref={scrollRef} style={{ flex: 1, minHeight: 0, overflowY: 'auto', paddingRight: 'var(--space-sm)' }}>
            {activeHours.map(h => (
              <section key={h} ref={el => { hourRefs.current[h] = el }} style={{ marginBottom: 'var(--space-md)' }}>
                <div style={{
                  position: 'sticky', top: 0, background: 'var(--bg)', zIndex: 1,
                  display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', padding: 'var(--space-xs) 0',
                }}>
                  <span style={{
                    fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-label)',
                    color: activeHour === h ? 'var(--accent)' : 'var(--muted)', fontWeight: 300,
                    fontFamily: 'var(--font-mono)', transition: 'color 0.2s ease',
                  }}>
                    {fmtHour(h)}
                  </span>
                  <span style={{ flex: 1, height: 1, background: activeHour === h ? 'var(--accent)' : 'var(--rule)', transition: 'background 0.2s ease' }} />
                </div>
                {byHour.get(h)!.map(act => (
                  <ActivityRow
                    key={act.id}
                    act={act}
                    selected={selected?.id === act.id}
                    onToggle={() => setSelected(selected?.id === act.id ? null : act)}
                  />
                ))}
              </section>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
