import { useTimelineFeed, ALL_CATEGORIES, ALL_STATES } from '../../hooks/useTimelineFeed'
import { stateInk, inkVar } from './minimalDesign'
import PageHeader from './PageHeader'
import Icon from './Icon'
import { Label, Pill, StateLabel, GhostButton, EmptyState } from './primitives'

// State is encoded by intensity (the row dot + state label); category is neutral.

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

function fmtRowTime(iso: string): { time: string; ampm: string } {
  const parts = new Date(iso)
    .toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
    .toLowerCase()
    .split(' ')
  return { time: parts[0] ?? '', ampm: parts[1] ?? '' }
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

  const subtitle = hasFilters
    ? `${filtered.length} of ${activities.length} activities · ${captures.length} captures`
    : `${captures.length} captures · ${activities.length} activities`

  return (
    <div style={{ padding: 'var(--space-lg)' }}>
      <PageHeader
        title="timeline"
        subtitle={subtitle}
        right={hasFilters ? <GhostButton onClick={clearFilters}>clear filters</GhostButton> : undefined}
      />

      {/* Search + filters */}
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
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {filtered.map(act => {
            const lvl = stateInk(act.productivity_state)
            const isSelected = selected?.id === act.id
            const { time, ampm } = fmtRowTime(act.started_at)
            return (
              <div key={act.id} style={{ borderTop: '1px solid var(--rule)' }}>
                <div
                  role="button" tabIndex={0}
                  onClick={() => setSelected(isSelected ? null : act)}
                  onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') setSelected(isSelected ? null : act) }}
                  style={{
                    display: 'grid', gridTemplateColumns: '64px 12px 1fr auto',
                    gap: 'var(--space-md)', alignItems: 'center',
                    padding: 'var(--space-md) 0', cursor: 'pointer',
                  }}
                >
                  <div style={{
                    fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-snug)',
                    color: 'var(--muted)', fontWeight: 300, whiteSpace: 'nowrap',
                  }}>
                    {time} <span style={{ opacity: 0.7 }}>{ampm}</span>
                  </div>
                  <span style={{
                    width: 8, height: 8, borderRadius: '50%',
                    background: inkVar(lvl), justifySelf: 'center',
                  }} />
                  <div style={{
                    fontSize: 'var(--text-md)', color: 'var(--fg)', fontWeight: 400,
                    overflow: 'hidden', textOverflow: 'ellipsis',
                    whiteSpace: isSelected ? 'normal' : 'nowrap',
                  }}>
                    {act.summary ?? '—'}
                  </div>
                  <div style={{ display: 'flex', gap: 'var(--space-xs)', alignItems: 'center' }}>
                    <Pill>{act.task_category ?? 'other'}</Pill>
                    <StateLabel state={act.productivity_state ?? '—'} level={lvl} />
                  </div>
                </div>
              </div>
            )
          })}
          <div style={{ borderTop: '1px solid var(--rule)' }} />
        </div>
      )}
    </div>
  )
}
