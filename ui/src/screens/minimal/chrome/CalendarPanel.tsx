import type { CSSProperties } from 'react'
import { useCalendarPanel } from '../../../hooks/useCalendarPanel'
import { Label } from '../primitives'
import Icon from '../Icon'

// 300px right panel, 1px left rule. Month grid (Su-first), selected day =
// --fg block / --bg text, future days faint, today carries the accent dot
// (the live "now" cue). Lowercase everywhere, set in content.

const MONTHS = [
  'january','february','march','april','may','june',
  'july','august','september','october','november','december',
]
const DAYS = ['su','mo','tu','we','th','fr','sa']

const navBtn: CSSProperties = {
  background: 'none', border: 'none', padding: 4, cursor: 'pointer',
  color: 'var(--muted)', display: 'flex', alignItems: 'center',
}

export default function CalendarPanel({ onClose }: { onClose: () => void }) {
  const {
    isChat, isActive,
    viewYear, viewMonth, cells,
    prevMonth, nextMonth, selectDay, goToToday,
    selectedDate, today, todayDate,
    selDay, isSelectedInView, isAtCurrentMonth,
    chatDateOverridden, setChatDateOverridden,
  } = useCalendarPanel()

  const now = new Date()
  const viewingLabel = isChat && chatDateOverridden
    ? 'no date filter'
    : new Date(selectedDate + 'T00:00:00')
        .toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
        .toLowerCase()

  return (
    <aside className="m-panel" style={{
      width: 'var(--panel-w)', flex: '0 0 auto', borderLeft: '1px solid var(--rule)',
      padding: 'var(--space-md)', display: 'flex', flexDirection: 'column',
      gap: 'var(--space-md)', boxSizing: 'border-box', overflowY: 'auto',
    }}>
      {/* Month navigator */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <button type="button" onClick={prevMonth} className="m-quiet" style={navBtn}>
          <Icon name="chevronL" size={15} />
        </button>
        <button
          type="button" onClick={goToToday} title="go to today"
          className="m-quiet"
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            fontSize: 'var(--text-sm)', color: 'var(--fg)', fontWeight: 400,
            letterSpacing: 'var(--tracking-wide)', fontFamily: 'var(--font-sans)',
          }}
        >
          {MONTHS[viewMonth]} {viewYear}
        </button>
        <button
          type="button" onClick={nextMonth} disabled={isAtCurrentMonth} className="m-quiet"
          style={{ ...navBtn, opacity: isAtCurrentMonth ? 0.3 : 1, cursor: isAtCurrentMonth ? 'default' : 'pointer' }}
        >
          <Icon name="chevronR" size={15} />
        </button>
      </div>

      {/* Day grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 2 }}>
        {DAYS.map(w => (
          <div key={w} style={{
            fontSize: '0.58rem', letterSpacing: 'var(--tracking-wide)', color: 'var(--muted)',
            textAlign: 'center', padding: '4px 0', fontWeight: 300,
          }}>
            {w}
          </div>
        ))}
        {cells.map((d, i) => {
          if (d == null) return <div key={`empty-${i}`} />
          const cellDate = new Date(viewYear, viewMonth, d)
          const future = cellDate > todayDate
          const selected = isActive && isSelectedInView && d === selDay
          const isToday = viewYear === now.getFullYear() && viewMonth === now.getMonth() && d === now.getDate()
          const interactive = isActive && !future
          return (
            <button
              key={i} type="button" disabled={!interactive} onClick={() => selectDay(d)}
              style={{
                aspectRatio: '1 / 1', display: 'flex', alignItems: 'center', justifyContent: 'center',
                border: 'none', cursor: interactive ? 'pointer' : 'default',
                fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-sans)',
                background: selected ? 'var(--fg)' : 'none',
                color: selected ? 'var(--bg)' : future ? 'var(--rule)' : 'var(--muted)',
                fontWeight: isToday && !selected ? 400 : 300,
                position: 'relative',
              }}
            >
              {d}
              {isToday && !selected && (
                <span style={{
                  position: 'absolute', bottom: 3, width: 3, height: 3,
                  borderRadius: '50%', background: 'var(--accent)',
                }} />
              )}
            </button>
          )
        })}
      </div>

      {/* Viewing card */}
      <div style={{
        border: '1px solid var(--rule)', padding: 'var(--space-sm) var(--space-sm)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--space-xs)',
      }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
          <Label>{isChat && chatDateOverridden ? 'all dates' : 'viewing'}</Label>
          <span style={{ fontSize: 'var(--text-base)', color: 'var(--fg)', fontWeight: 400, whiteSpace: 'nowrap' }}>
            {viewingLabel}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, flex: '0 0 auto' }}>
          {isChat && !chatDateOverridden && (
            <button
              type="button" onClick={() => setChatDateOverridden(true)} className="m-quiet"
              title="remove date filter — search all history"
              style={{
                background: 'none', border: 'none', cursor: 'pointer', padding: '2px 4px',
                fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-wide)', fontFamily: 'var(--font-sans)',
              }}
            >
              all dates
            </button>
          )}
          {isChat && chatDateOverridden && (
            <button
              type="button" onClick={() => setChatDateOverridden(false)} className="m-quiet"
              style={{
                background: 'none', border: 'none', cursor: 'pointer', padding: '2px 4px',
                fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-wide)', fontFamily: 'var(--font-sans)',
              }}
            >
              restore
            </button>
          )}
          {(!isChat || chatDateOverridden) && selectedDate !== today && (
            <button
              type="button" onClick={goToToday} className="m-quiet"
              style={{
                background: 'none', border: 'none', cursor: 'pointer', padding: '2px 4px',
                fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-wide)', fontFamily: 'var(--font-sans)',
              }}
            >
              today
            </button>
          )}
          <button type="button" onClick={onClose} className="m-quiet" style={navBtn}>
            <Icon name="close" size={14} />
          </button>
        </div>
      </div>
    </aside>
  )
}
