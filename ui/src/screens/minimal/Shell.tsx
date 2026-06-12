import { useState, type ReactNode } from 'react'
import Sidebar from './chrome/Sidebar'
import TopBar from './chrome/TopBar'
import CalendarPanel from './chrome/CalendarPanel'
import DebugPanel from './chrome/DebugPanel'

// Minimal app chrome: fixed 180px sidebar, 52px top bar spanning the area
// right of it, routed content, optional 300px right panels.

export default function Shell({ calendarApplies, children }: { calendarApplies: boolean; children: ReactNode }) {
  const [calendarOpen, setCalendarOpen] = useState(false)
  const [debugOpen, setDebugOpen] = useState(false)
  const calOpen = calendarApplies && calendarOpen

  return (
    <div style={{
      display: 'flex', height: '100vh', overflow: 'hidden',
      background: 'var(--bg)', color: 'var(--fg)',
    }}>
      <Sidebar
        calendarApplies={calendarApplies}
        calendarOpen={calOpen}
        onToggleCalendar={() => setCalendarOpen(v => !v)}
        debugOpen={debugOpen}
        onToggleDebug={() => setDebugOpen(v => !v)}
      />
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <TopBar />
        <div style={{ flex: 1, minHeight: 0, display: 'flex' }}>
          <main style={{ flex: 1, minWidth: 0, overflowY: 'auto' }}>
            {children}
          </main>
          {calOpen && <CalendarPanel onClose={() => setCalendarOpen(false)} />}
          {debugOpen && <DebugPanel onClose={() => setDebugOpen(false)} />}
        </div>
      </div>
    </div>
  )
}
