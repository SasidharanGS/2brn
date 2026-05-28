import { useState, useMemo } from 'react'
import { useLocation } from 'react-router-dom'
import { useAppDate, toDateStr } from '../../context/DateContext'

// Routes where the calendar panel is shown
const CALENDAR_ROUTES = ['/chat', '/journal', '/blog', '/timeline', '/insights']

const MONTHS = [
  'January','February','March','April','May','June',
  'July','August','September','October','November','December',
]
const DAYS = ['Su','Mo','Tu','We','Th','Fr','Sa']

function getDaysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate()
}

function getFirstDayOfMonth(year: number, month: number) {
  return new Date(year, month, 1).getDay()
}

export default function CalendarPanel() {
  const location = useLocation()
  const { selectedDate, setSelectedDate, chatDateOverridden, setChatDateOverridden } = useAppDate()
  const isChat = location.pathname === '/chat'

  // Derive view month from the selected date
  const [viewYear, setViewYear] = useState(() => {
    const d = new Date(selectedDate + 'T00:00:00')
    return d.getFullYear()
  })
  const [viewMonth, setViewMonth] = useState(() => {
    const d = new Date(selectedDate + 'T00:00:00')
    return d.getMonth()
  })

  const today = toDateStr(new Date())
  const todayDate = new Date(today + 'T00:00:00')

  // Is the calendar active on the current route?
  const isActive = CALENDAR_ROUTES.some(r => location.pathname === r)

  const daysInMonth = getDaysInMonth(viewYear, viewMonth)
  const firstDay = getFirstDayOfMonth(viewYear, viewMonth)

  // Build grid cells: leading empty cells + day cells
  const cells = useMemo(() => {
    const result: (number | null)[] = []
    for (let i = 0; i < firstDay; i++) result.push(null)
    for (let d = 1; d <= daysInMonth; d++) result.push(d)
    // Pad to complete last row
    while (result.length % 7 !== 0) result.push(null)
    return result
  }, [viewYear, viewMonth, firstDay, daysInMonth])

  function prevMonth() {
    if (viewMonth === 0) { setViewMonth(11); setViewYear(y => y - 1) }
    else setViewMonth(m => m - 1)
  }

  function nextMonth() {
    const now = new Date()
    // Don't navigate beyond current month
    if (viewYear === now.getFullYear() && viewMonth === now.getMonth()) return
    if (viewMonth === 11) { setViewMonth(0); setViewYear(y => y + 1) }
    else setViewMonth(m => m + 1)
  }

  function selectDay(day: number) {
    if (!isActive) return
    const d = new Date(viewYear, viewMonth, day)
    if (d > todayDate) return // no future dates
    const str = toDateStr(d)
    setSelectedDate(str)
  }

  function goToToday() {
    const now = new Date()
    setViewYear(now.getFullYear())
    setViewMonth(now.getMonth())
    setSelectedDate(today)
  }

  // Parse selected date for highlighting
  const selDate = new Date(selectedDate + 'T00:00:00')
  const selYear = selDate.getFullYear()
  const selMonth = selDate.getMonth()
  const selDay = selDate.getDate()
  const isSelectedInView = selYear === viewYear && selMonth === viewMonth

  const now = new Date()
  const isAtCurrentMonth = viewYear === now.getFullYear() && viewMonth === now.getMonth()

  return (
    <div
      className="flex flex-col shrink-0 border-l"
      style={{
        width: 216,
        background: 'var(--bg-surface)',
        borderColor: 'var(--border)',
      }}
    >
      {/* Month navigator */}
      <div className="px-3 pt-3 pb-1 shrink-0">
        <div className="flex items-center justify-between mb-2.5">
          <button
            onClick={prevMonth}
            className="w-6 h-6 flex items-center justify-center rounded-md transition-all duration-100 hover:opacity-80"
            style={{ color: 'var(--text-muted)', background: 'var(--bg-surface-2)' }}
          >
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
              <path d="M6.5 2L3.5 5L6.5 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>

          <button
            onClick={goToToday}
            className="text-[12px] font-semibold tracking-tight transition-colors hover:opacity-80"
            style={{ color: 'var(--text)' }}
            title="Go to today"
          >
            {MONTHS[viewMonth].slice(0, 3)} {viewYear}
          </button>

          <button
            onClick={nextMonth}
            className="w-6 h-6 flex items-center justify-center rounded-md transition-all duration-100 hover:opacity-80"
            style={{
              color: isAtCurrentMonth ? 'var(--text-dim)' : 'var(--text-muted)',
              background: 'var(--bg-surface-2)',
              opacity: isAtCurrentMonth ? 0.3 : 1,
              cursor: isAtCurrentMonth ? 'default' : 'pointer',
            }}
            disabled={isAtCurrentMonth}
          >
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
              <path d="M3.5 2L6.5 5L3.5 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>

        {/* Day-of-week headers */}
        <div className="grid grid-cols-7 mb-1">
          {DAYS.map(d => (
            <div
              key={d}
              className="text-center text-[10px] font-medium py-0.5"
              style={{ color: 'var(--text-dim)' }}
            >
              {d}
            </div>
          ))}
        </div>

        {/* Day grid */}
        <div className="grid grid-cols-7 gap-y-0.5">
          {cells.map((day, i) => {
            if (!day) return <div key={`empty-${i}`} />

            const cellDate = new Date(viewYear, viewMonth, day)
            const isFuture = cellDate > todayDate
            const isToday = viewYear === now.getFullYear() && viewMonth === now.getMonth() && day === now.getDate()
            const isSelected = isActive && isSelectedInView && day === selDay
            const isInteractive = isActive && !isFuture

            return (
              <button
                key={day}
                onClick={() => selectDay(day)}
                disabled={!isInteractive}
                className="relative flex items-center justify-center rounded-md text-[12px] font-medium transition-all duration-100"
                style={{
                  height: 26,
                  cursor: isInteractive ? 'pointer' : 'default',
                  background: isSelected
                    ? 'var(--accent)'
                    : isToday && !isSelected
                    ? 'var(--accent-glow)'
                    : 'transparent',
                  color: isSelected
                    ? 'var(--toggle-knob)'
                    : isFuture
                    ? 'var(--text-dim)'
                    : isToday
                    ? 'var(--accent)'
                    : 'var(--text-muted)',
                  fontWeight: isToday || isSelected ? 600 : 400,
                  opacity: isFuture ? 0.3 : 1,
                }}
                onMouseEnter={e => {
                  if (isInteractive && !isSelected) {
                    (e.currentTarget as HTMLButtonElement).style.background = 'var(--bg-surface-3)'
                  }
                }}
                onMouseLeave={e => {
                  if (isInteractive && !isSelected) {
                    (e.currentTarget as HTMLButtonElement).style.background = 'transparent'
                  }
                }}
              >
                {day}
                {/* Today dot */}
                {isToday && !isSelected && (
                  <span
                    className="absolute bottom-0.5 left-1/2 w-1 h-1 rounded-full"
                    style={{ background: 'var(--accent)', transform: 'translateX(-50%)' }}
                  />
                )}
              </button>
            )
          })}
        </div>
      </div>

      {/* Selected date display */}
      <div
        className="mx-3 mt-2 mb-3 px-2.5 py-2 rounded-[9px] shrink-0"
        style={{ background: 'var(--bg-surface-2)', borderColor: 'var(--border)' }}
      >
        {isActive ? (
          <div className="flex items-center justify-between">
            <div>
              <div className="text-[10px] uppercase tracking-widest font-medium mb-0.5" style={{ color: 'var(--text-dim)' }}>
                {isChat && chatDateOverridden ? 'All dates' : 'Viewing'}
              </div>
              <div className="text-[12px] font-semibold" style={{ color: isChat && chatDateOverridden ? 'var(--text-muted)' : 'var(--accent)' }}>
                {isChat && chatDateOverridden
                  ? 'No date filter'
                  : new Date(selectedDate + 'T00:00:00').toLocaleDateString('en-GB', {
                      day: 'numeric', month: 'short', year: 'numeric'
                    })
                }
              </div>
            </div>
            <div className="flex items-center gap-1.5">
              {/* ✕ to clear date filter — Chat only */}
              {isChat && !chatDateOverridden && (
                <button
                  onClick={() => setChatDateOverridden(true)}
                  className="text-[10px] w-5 h-5 flex items-center justify-center rounded-full transition-all hover:opacity-80"
                  style={{ background: 'rgba(255,255,255,0.08)', color: 'var(--text-dim)' }}
                  title="Remove date filter — search all history"
                >
                  ✕
                </button>
              )}
              {/* Restore date filter when overridden in Chat */}
              {isChat && chatDateOverridden && (
                <button
                  onClick={() => setChatDateOverridden(false)}
                  className="text-[10px] px-2 py-1 rounded-[6px] transition-colors hover:opacity-80"
                  style={{ background: 'var(--accent-glow)', color: 'var(--accent)', border: '1px solid rgba(129,140,248,0.2)' }}
                >
                  Restore
                </button>
              )}
              {/* Today shortcut — non-Chat only (or when override is active) */}
              {(!isChat || chatDateOverridden) && selectedDate !== today && (
                <button
                  onClick={goToToday}
                  className="text-[10px] px-2 py-1 rounded-[6px] transition-colors hover:opacity-80"
                  style={{ background: 'var(--accent-glow)', color: 'var(--accent)', border: '1px solid rgba(129,140,248,0.2)' }}
                >
                  Today
                </button>
              )}
            </div>
          </div>
        ) : (
          <p className="text-[10px] text-center" style={{ color: 'var(--text-dim)' }}>
            Navigate to a section to use the calendar
          </p>
        )}
      </div>

      {/* Spacer to push content up */}
      <div className="flex-1" />

    </div>
  )
}
