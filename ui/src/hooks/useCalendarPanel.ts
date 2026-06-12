import { useState, useMemo, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { useAppDate, toDateStr } from '../context/DateContext'

// Routes where the calendar panel is shown
export const CALENDAR_ROUTES = ['/chat', '/journal', '/blog', '/timeline', '/insights']

function getDaysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate()
}

function getFirstDayOfMonth(year: number, month: number) {
  return new Date(year, month, 1).getDay()
}

/** Calendar panel state: visible month, day grid, selection, chat date override. */
export function useCalendarPanel() {
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

  // Sync the visible month when selectedDate changes from outside (e.g. another
  // section, or a "Today" reset). In-calendar prev/next don't touch selectedDate,
  // so the user's own navigation is preserved.
  useEffect(() => {
    const d = new Date(selectedDate + 'T00:00:00')
    setViewYear(d.getFullYear())
    setViewMonth(d.getMonth())
  }, [selectedDate])

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
    setSelectedDate(toDateStr(d))
  }

  function goToToday() {
    const now = new Date()
    setViewYear(now.getFullYear())
    setViewMonth(now.getMonth())
    setSelectedDate(today)
  }

  // Parse selected date for highlighting
  const selDate = new Date(selectedDate + 'T00:00:00')
  const isSelectedInView = selDate.getFullYear() === viewYear && selDate.getMonth() === viewMonth
  const selDay = selDate.getDate()

  const now = new Date()
  const isAtCurrentMonth = viewYear === now.getFullYear() && viewMonth === now.getMonth()

  return {
    isChat, isActive,
    viewYear, viewMonth, cells,
    prevMonth, nextMonth, selectDay, goToToday,
    selectedDate, today, todayDate,
    selDay, isSelectedInView, isAtCurrentMonth,
    chatDateOverridden, setChatDateOverridden,
  }
}
