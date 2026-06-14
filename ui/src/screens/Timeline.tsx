import type { CSSProperties } from 'react'
import { categoryChip, stateChip } from '../utils/design'
import { fmtDur } from '../utils/time'
import { fmtHour } from '../utils/timeline'
import type { ActivityRecord, SessionsResponse } from '../api/types'
import { useTimelineFeed, ALL_CATEGORIES, ALL_STATES } from '../hooks/useTimelineFeed'
import { useHourScroll } from '../hooks/useHourScroll'
import { stateInk, inkVar } from './minimal/minimalDesign'
import { PageHeader, Button, SectionLabel, EmptyState, Icon, useKit } from '../ui-kit'

// Unified Timeline. The hour-rail interaction (scroll-spy, goToHour, refs) lives
// in useHourScroll — shared once. The visuals genuinely diverge (colour-coded
// lanes/cards vs monochrome bar/rows), so those are per-skin leaves below.

const fmtClock = (ts: number | string) =>
  new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

function fmtRowTime(iso: string): { time: string; ampm: string } {
  const parts = new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }).toLowerCase().split(' ')
  return { time: parts[0] ?? '', ampm: parts[1] ?? '' }
}

/** Graduated grey for the minimal category bar (NOT the productivity ink ramp). */
function bandTint(rank: number, total: number): string {
  const pct = Math.round(70 - (rank / Math.max(total - 1, 1)) * 48)
  return `color-mix(in oklab, var(--fg) ${pct}%, var(--bg))`
}

// ── Session visualisation: modern per-monitor lanes / minimal stacked bar ──────
function SessionViz({ sessions }: { sessions: SessionsResponse }) {
  const { skin } = useKit()
  return skin === 'minimal' ? <CategoryBar sessions={sessions} /> : <SessionLanes sessions={sessions} />
}

function SessionLanes({ sessions }: { sessions: SessionsResponse }) {
  const { blocks, totals } = sessions
  if (blocks.length === 0) return null
  const t0 = Math.min(...blocks.map(b => Date.parse(b.start)))
  const t1 = Math.max(...blocks.map(b => Date.parse(b.end)))
  const span = Math.max(t1 - t0, 1)
  const monitors = [...new Set(blocks.map(b => b.monitor_index))].sort((a, b) => a - b)
  const catTotals = Object.entries(totals.by_category).sort((a, b) => b[1] - a[1])
  return (
    <div style={{ background: 'var(--k-surface)', border: '1px solid var(--k-rule)', borderRadius: 'var(--k-radius)', padding: 16, marginBottom: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <SectionLabel>Blocks</SectionLabel>
        <span style={{ fontSize: 11, fontFamily: 'var(--k-font-mono)', color: 'var(--k-dim)' }}>{fmtDur(totals.observed_seconds)} on screen</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {monitors.map(m => (
          <div key={m} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {monitors.length > 1 && <span style={{ fontSize: 10, fontFamily: 'var(--k-font-mono)', width: 24, flexShrink: 0, textAlign: 'right', color: 'var(--k-dim)' }}>M{m}</span>}
            <div style={{ position: 'relative', height: 24, flex: 1, borderRadius: 6, overflow: 'hidden', background: 'var(--k-surface-2)' }}>
              {blocks.filter(b => b.monitor_index === m).map((b, i) => {
                const chip = categoryChip(b.task_category)
                const left = ((Date.parse(b.start) - t0) / span) * 100
                const width = Math.max(((Date.parse(b.end) - Date.parse(b.start)) / span) * 100, 0.35)
                const tip = [`${b.app_name ?? 'unknown'} · ${b.task_category ?? 'other'} · ${fmtDur(b.duration_seconds)}`, `${fmtClock(b.start)}–${fmtClock(b.end)}`, b.summary ?? ''].filter(Boolean).join('\n')
                return <div key={i} title={tip} style={{ position: 'absolute', top: 0, height: '100%', left: `${left}%`, width: `${width}%`, background: chip.dot, opacity: 0.85 }} />
              })}
            </div>
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6, fontSize: 10, fontFamily: 'var(--k-font-mono)', color: 'var(--k-dim)' }}>
        <span>{fmtClock(t0)}</span><span>{fmtClock(t1)}</span>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 12 }}>
        {catTotals.map(([cat, secs]) => {
          const chip = categoryChip(cat)
          return (
            <span key={cat} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 10px', borderRadius: 999, fontSize: 11, fontWeight: 500, background: chip.bg, color: chip.text }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: chip.dot }} />{cat} {fmtDur(secs)}
            </span>
          )
        })}
      </div>
    </div>
  )
}

function CategoryBar({ sessions }: { sessions: SessionsResponse }) {
  const { observed_seconds, by_category } = sessions.totals
  const cats = Object.entries(by_category).filter(([, s]) => s > 0).sort((a, b) => b[1] - a[1])
  if (cats.length === 0 || observed_seconds <= 0) return null
  const tint = (i: number) => bandTint(i, cats.length)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--k-space-sm)' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 'var(--k-space-sm)' }}>
        <SectionLabel>By category</SectionLabel>
        <span style={{ fontSize: 'var(--k-text-meta)', color: 'var(--k-muted)', fontFamily: 'var(--k-font-mono)' }}>{fmtDur(observed_seconds)} on screen</span>
      </div>
      <div style={{ display: 'flex', height: 10, border: '1px solid var(--k-rule)', gap: 1, background: 'var(--k-rule)' }}>
        {cats.map(([cat, secs], i) => <div key={cat} title={`${cat} · ${fmtDur(secs)}`} style={{ flex: `${Math.max(secs, 1)} 0 0`, background: tint(i), minWidth: 2 }} />)}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--k-space-sm)' }}>
        {cats.map(([cat, secs], i) => (
          <span key={cat} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 'var(--k-text-meta)', color: 'var(--k-muted)' }}>
            <span aria-hidden="true" style={{ width: 7, height: 7, background: tint(i), flex: '0 0 auto' }} />{cat} <span style={{ color: 'var(--k-fg)' }}>{fmtDur(secs)}</span>
          </span>
        ))}
      </div>
    </div>
  )
}

// ── Hour rail tick — shared; `level` (minimal) tints the line with the ink ramp ─
function HourTick({ hour, has, level, count, isActive, isHover, onClick, onEnter, onLeave }: {
  hour: number; has: boolean; level?: number; count: number
  isActive: boolean; isHover: boolean; onClick: () => void; onEnter: () => void; onLeave: () => void
}) {
  const lit = isActive || isHover
  const lineColor = lit ? 'var(--k-accent)' : has ? (level != null ? inkVar(level) : 'var(--k-muted)') : 'var(--k-rule)'
  const lineW = isHover ? 44 : has ? Math.min(16 + count * 6, 34) : 12
  return (
    <button type="button" onClick={onClick} onMouseEnter={onEnter} onMouseLeave={onLeave} title={fmtHour(hour)}
      style={{ display: 'flex', alignItems: 'center', gap: 10, height: 26, width: '100%', background: 'none', border: 'none', padding: 0, cursor: 'pointer' }}>
      <span aria-hidden="true" style={{ height: lit || has ? 2 : 1, width: lineW, background: lineColor, flex: '0 0 auto', borderRadius: 1, transition: 'width 0.18s ease, background 0.18s ease, height 0.18s ease' }} />
      <span style={{ fontSize: 10, letterSpacing: '0.05em', whiteSpace: 'nowrap', pointerEvents: 'none', fontFamily: 'var(--k-font-mono)', color: isActive ? 'var(--k-fg)' : 'var(--k-dim)', opacity: lit ? 1 : 0, transition: 'opacity 0.18s ease' }}>
        {fmtHour(hour)}
      </span>
    </button>
  )
}

// ── Activity row — modern card / minimal grid ─────────────────────────────────
function TimelineRow({ act, selected, onToggle }: { act: ActivityRecord; selected: boolean; onToggle: () => void }) {
  const { skin } = useKit()
  if (skin === 'minimal') {
    const lvl = stateInk(act.productivity_state)
    const { time, ampm } = fmtRowTime(act.started_at)
    return (
      <div role="button" tabIndex={0} onClick={onToggle} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') onToggle() }}
        style={{ display: 'grid', gridTemplateColumns: '68px 12px 1fr auto', gap: 'var(--k-space-md)', alignItems: 'center', borderTop: '1px solid var(--k-rule)', padding: 'var(--k-space-sm) 0', cursor: 'pointer' }}>
        <div style={{ fontSize: 'var(--k-text-meta)', color: 'var(--k-muted)', whiteSpace: 'nowrap', fontFamily: 'var(--k-font-mono)' }}>
          {time} <span style={{ opacity: 0.7 }}>{ampm}</span>
        </div>
        <span style={{ width: 8, height: 8, borderRadius: '50%', background: inkVar(lvl), justifySelf: 'center' }} />
        <div style={{ fontSize: 'var(--k-text-title)', color: 'var(--k-fg)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: selected ? 'normal' : 'nowrap' }}>{act.summary ?? '—'}</div>
        <div style={{ display: 'flex', gap: 'var(--k-space-xs)', alignItems: 'center' }}>
          <span style={{ background: 'var(--pill-bg)', color: 'var(--k-muted)', borderRadius: 'var(--k-radius-pill)', padding: '2px 7px', fontSize: 'var(--k-text-meta)', whiteSpace: 'nowrap' }}>{act.task_category ?? 'other'}</span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 'var(--k-text-meta)', color: 'var(--k-muted)', whiteSpace: 'nowrap' }}>
            <span aria-hidden="true" style={{ width: 7, height: 7, background: inkVar(lvl), flex: '0 0 auto' }} />{act.productivity_state ?? '—'}
          </span>
        </div>
      </div>
    )
  }
  const cc = categoryChip(act.task_category)
  const sc = stateChip(act.productivity_state)
  return (
    <button onClick={onToggle} style={{
      width: '100%', textAlign: 'left', borderRadius: 'var(--k-radius-sm)', border: '1px solid', padding: '12px 16px', cursor: 'pointer',
      transition: 'all 0.15s ease', background: selected ? 'var(--bg-surface-2)' : 'var(--bg-surface)',
      borderColor: selected ? 'rgba(129,140,248,0.4)' : 'var(--border)', boxShadow: selected ? '0 0 0 1px rgba(129,140,248,0.2)' : 'none',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span style={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0, background: cc.dot }} />
        <span style={{ fontSize: 11, fontFamily: 'var(--k-font-mono)', width: 40, flexShrink: 0, color: 'var(--text-dim)' }}>{new Date(act.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
        <span style={{ fontSize: 14, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--text)' }}>{act.summary ?? '—'}</span>
        <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 999, fontWeight: 500, flexShrink: 0, background: cc.bg, color: cc.text }}>{act.task_category ?? 'other'}</span>
        <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 999, flexShrink: 0, background: sc.bg, color: sc.text }}>{act.productivity_state ?? '—'}</span>
      </div>
      {selected && act.summary && (
        <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border)', fontSize: 13, lineHeight: 1.6, color: 'var(--text-muted)' }}>{act.summary}</div>
      )}
    </button>
  )
}

export default function Timeline() {
  const {
    selectedDate, activities, captures, sessions, loading,
    filtered, presentCategories, presentStates,
    selected, setSelected, categoryFilter, setCategoryFilter,
    stateFilter, setStateFilter, search, setSearch, hasFilters, clearFilters,
  } = useTimelineFeed()
  const { skin } = useKit()
  const { byHour, activeHours, railHours, activeHour, hoverHour, setHoverHour, goToHour, scrollRef, setHourRef } = useHourScroll(filtered)

  const hourLevel = (h: number) => {
    const bucket = byHour.get(h)
    return bucket ? Math.max(...bucket.map(a => stateInk(a.productivity_state))) : 0
  }

  const subtitle = hasFilters
    ? `${filtered.length} of ${activities.length} activities · ${captures.length} captures`
    : `${captures.length} captures · ${activities.length} activities`

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: 'var(--k-page-pad)', boxSizing: 'border-box' }}>
      <div style={{ flex: '0 0 auto' }}>
        <PageHeader
          title="Timeline" subtitle={subtitle}
          right={hasFilters ? <Button onClick={clearFilters}>Clear filters</Button> : undefined}
        />
        {!loading && sessions && <div style={{ marginBottom: 'var(--k-space-md)' }}><SessionViz sessions={sessions} /></div>}
        {!loading && activities.length > 0 && (
          <TimelineFilters
            skin={skin} search={search} setSearch={setSearch}
            categoryFilter={categoryFilter} setCategoryFilter={setCategoryFilter}
            stateFilter={stateFilter} setStateFilter={setStateFilter}
            presentCategories={presentCategories} presentStates={presentStates}
          />
        )}
      </div>

      {loading ? (
        <div style={{ fontSize: 'var(--k-text-body)', color: 'var(--k-muted)' }}>Loading…</div>
      ) : activities.length === 0 ? (
        <EmptyState icon="timeline" title={`No activity recorded for ${selectedDate}`} />
      ) : filtered.length === 0 ? (
        <EmptyState icon="insights" title="No activities match the current filters">
          <Button variant="soft" onClick={clearFilters}>Clear filters</Button>
        </EmptyState>
      ) : (
        <div style={{ flex: 1, minHeight: 0, display: 'flex', gap: 'var(--k-space-lg)' }}>
          <div style={{ flex: '0 0 auto', display: 'flex', flexDirection: 'column', gap: 2, paddingTop: 'var(--k-space-sm)', paddingRight: 'var(--k-space-md)', borderRight: '1px solid var(--k-rule)', overflowY: 'auto' }}>
            {railHours.map(h => (
              <HourTick key={h} hour={h} has={byHour.has(h)} count={byHour.get(h)?.length ?? 0}
                level={skin === 'minimal' ? hourLevel(h) : undefined}
                isActive={activeHour === h} isHover={hoverHour === h}
                onClick={() => goToHour(h)} onEnter={() => setHoverHour(h)} onLeave={() => setHoverHour(null)} />
            ))}
          </div>
          <div ref={scrollRef} style={{ flex: 1, minHeight: 0, overflowY: 'auto', paddingRight: 'var(--k-space-sm)' }}>
            {activeHours.map(h => (
              <section key={h} ref={el => setHourRef(h, el)} style={{ marginBottom: 'var(--k-space-md)' }}>
                <div style={{ position: 'sticky', top: 0, background: 'var(--k-bg)', zIndex: 1, display: 'flex', alignItems: 'center', gap: 'var(--k-space-sm)', padding: 'var(--k-space-xs) 0' }}>
                  <span style={{ fontSize: 10, letterSpacing: '0.1em', fontFamily: 'var(--k-font-mono)', color: activeHour === h ? 'var(--k-accent)' : 'var(--k-dim)', transition: 'color 0.2s ease' }}>{fmtHour(h)}</span>
                  <span style={{ flex: 1, height: 1, background: activeHour === h ? 'var(--k-accent)' : 'var(--k-rule)', transition: 'background 0.2s ease' }} />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: skin === 'minimal' ? 0 : 6, paddingTop: 6 }}>
                  {byHour.get(h)!.map(act => (
                    <TimelineRow key={act.id} act={act} selected={selected?.id === act.id} onToggle={() => setSelected(selected?.id === act.id ? null : act)} />
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

// ── Filter bar — modern colour-coded chips / minimal monochrome pills ─────────
function TimelineFilters({ skin, search, setSearch, categoryFilter, setCategoryFilter, stateFilter, setStateFilter, presentCategories, presentStates }: {
  skin: string; search: string; setSearch: (v: string) => void
  categoryFilter: string | null; setCategoryFilter: (v: never | null) => void
  stateFilter: string | null; setStateFilter: (v: never | null) => void
  presentCategories: Set<string | null>; presentStates: Set<string | null>
}) {
  if (skin === 'minimal') {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--k-space-md)', marginBottom: 'var(--k-space-lg)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--k-space-sm)', border: '1px solid var(--k-rule)', padding: 'var(--k-space-sm) var(--k-space-md)' }}>
          <span style={{ color: 'var(--k-muted)' }}><Icon name="search" size={15} /></span>
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="search activities…"
            style={{ flex: 1, background: 'none', border: 'none', outline: 'none', color: 'var(--k-fg)', fontSize: 'var(--k-text-body)', fontWeight: 'var(--k-body-weight)' as CSSProperties['fontWeight'], fontFamily: 'var(--k-font)' }} />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: 'var(--k-space-sm) var(--k-space-md)', alignItems: 'center' }}>
          <SectionLabel>Category</SectionLabel>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--k-space-xs)' }}>
            {ALL_CATEGORIES.map(c => <MonoPill key={c} label={c} active={categoryFilter === c} present={presentCategories.has(c)} onClick={() => setCategoryFilter((categoryFilter === c ? null : c) as never)} />)}
          </div>
          <SectionLabel>State</SectionLabel>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--k-space-xs)' }}>
            {ALL_STATES.map(s => <MonoPill key={s} label={s === 'in-meeting' ? 'meeting' : s} dot level={stateInk(s)} active={stateFilter === s} present={presentStates.has(s)} onClick={() => setStateFilter((stateFilter === s ? null : s) as never)} />)}
          </div>
        </div>
      </div>
    )
  }
  return (
    <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 12, padding: 12, marginBottom: 20, display: 'flex', flexDirection: 'column', gap: 10 }}>
      <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search activities…"
        style={{ width: '100%', borderRadius: 8, border: `1px solid ${search ? 'var(--accent)' : 'var(--border-2)'}`, padding: '6px 12px', fontSize: 13, outline: 'none', background: 'var(--bg-input)', color: 'var(--text)' }} />
      <ChipRow label="Category" items={ALL_CATEGORIES} active={categoryFilter} present={presentCategories} onToggle={c => setCategoryFilter((categoryFilter === c ? null : c) as never)} color={categoryChip} />
      <ChipRow label="State" items={ALL_STATES} active={stateFilter} present={presentStates} onToggle={s => setStateFilter((stateFilter === s ? null : s) as never)} color={stateChip} relabel={s => (s === 'in-meeting' ? 'meeting' : s)} dot={false} />
    </div>
  )
}

function ChipRow({ label, items, active, present, onToggle, color, relabel, dot = true }: {
  label: string; items: readonly string[]; active: string | null; present: Set<string | null>
  onToggle: (v: string) => void; color: (k: string) => { bg: string; text: string; dot?: string }
  relabel?: (v: string) => string; dot?: boolean
}) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
      <span style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.1em', marginRight: 4, fontWeight: 500, color: 'var(--text-dim)' }}>{label}</span>
      {items.map(it => {
        const chip = color(it)
        const isActive = active === it
        const has = present.has(it)
        return (
          <button key={it} disabled={!has} onClick={() => onToggle(it)}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 10px', borderRadius: 999, fontSize: 11, fontWeight: 500, cursor: has ? 'pointer' : 'default', opacity: has ? 1 : 0.4,
              background: isActive ? chip.bg : 'var(--bg-surface-2)', color: isActive ? chip.text : has ? 'var(--text-muted)' : 'var(--text-dim)', border: isActive ? `1px solid ${chip.text}40` : '1px solid var(--border)' }}>
            {dot && <span style={{ width: 6, height: 6, borderRadius: '50%', background: chip.dot }} />}
            {relabel ? relabel(it) : it}
          </button>
        )
      })}
    </div>
  )
}

function MonoPill({ label, active, present, dot, level, onClick }: {
  label: string; active: boolean; present: boolean; dot?: boolean; level?: number; onClick: () => void
}) {
  return (
    <button type="button" onClick={onClick} disabled={!present} className={active ? undefined : 'm-pill-btn'}
      style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: active ? 'var(--k-fg)' : 'none', color: active ? 'var(--k-bg)' : 'var(--k-muted)',
        border: `1px solid ${active ? 'var(--k-fg)' : 'var(--k-rule)'}`, borderRadius: 'var(--k-radius-pill)', padding: '3px 10px', cursor: present ? 'pointer' : 'default',
        fontSize: 'var(--k-text-meta)', fontWeight: 'var(--k-body-weight)' as CSSProperties['fontWeight'], fontFamily: 'var(--k-font)', opacity: present ? 1 : 0.4 }}>
      {dot && <span style={{ width: 6, height: 6, flex: '0 0 auto', background: active ? 'var(--k-bg)' : inkVar(level ?? 0) }} />}
      {label}
    </button>
  )
}
