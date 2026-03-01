import { useState, useEffect, useCallback } from 'react'
import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import Dashboard   from './components/Dashboard'
import Chat        from './components/Chat'
import Journal     from './components/Journal'
import Blog        from './components/Blog'
import Timeline    from './components/Timeline'
import Insights    from './components/Insights'
import Settings    from './components/Settings'
import Instructions from './components/Instructions'
import DaemonStatus  from './components/shared/DaemonStatus'
import StatsBar      from './components/shared/StatsBar'
import DebugPanel    from './components/shared/DebugPanel'
import CalendarPanel from './components/shared/CalendarPanel'
import { DateProvider } from './context/DateContext'

const NAV = [
  { to: '/',              label: 'Home',         icon: '🏠',  end: true },
  { to: '/chat',          label: 'Chat',         icon: '💬' },
  { to: '/journal',       label: 'Journal',      icon: '📔' },
  { to: '/blog',          label: 'Blog',         icon: '✍' },
  { to: '/timeline',      label: 'Timeline',     icon: '🕐' },
  { to: '/insights',      label: 'Insights',     icon: '💡' },
  { to: '/instructions',  label: 'Instructions', icon: '📋' },
  { to: '/settings',      label: 'Settings',     icon: '⚙️' },
]

type ThemeMode = 'light' | 'system' | 'dark'
const THEME_KEY = '2brn-theme-mode'

function readPersistedMode(): ThemeMode {
  try {
    const v = localStorage.getItem(THEME_KEY)
    if (v === 'light' || v === 'system' || v === 'dark') return v
  } catch {}
  return 'system'
}

export default function App() {
  const location = useLocation()
  const [debugOpen, setDebugOpen]       = useState(false)
  const [calendarOpen, setCalendarOpen] = useState(true)

  const [themeMode, setThemeModeState] = useState<ThemeMode>(readPersistedMode)

  const applyThemeClass = useCallback((osIsDark: boolean, mode: ThemeMode) => {
    const isDark = mode === 'dark' || (mode === 'system' && osIsDark)
    document.documentElement.classList.toggle('light', !isDark)
  }, [])

  useEffect(() => {
    window.electronAPI.getTheme().then(osTheme =>
      applyThemeClass(osTheme === 'dark', readPersistedMode())
    )
    window.electronAPI.onThemeChanged(osTheme => {
      setThemeModeState(current => {
        applyThemeClass(osTheme === 'dark', current)
        return current
      })
    })
    window.electronAPI.getPlatform().then(platform => {
      document.documentElement.classList.toggle('macos', platform === 'darwin')
    })
  }, [applyThemeClass])

  const handleThemeModeChange = useCallback((mode: ThemeMode) => {
    try { localStorage.setItem(THEME_KEY, mode) } catch {}
    setThemeModeState(mode)
    if (mode === 'light') {
      document.documentElement.classList.add('light')
    } else if (mode === 'dark') {
      document.documentElement.classList.remove('light')
    } else {
      window.electronAPI.getTheme().then(osTheme => applyThemeClass(osTheme === 'dark', 'system'))
    }
  }, [applyThemeClass])

  // Calendar is irrelevant on Home and Settings — hide toggle and panel
  const calendarApplies = location.pathname !== '/' && location.pathname !== '/settings'

  return (
    <DateProvider>
      <div className="flex flex-col h-screen overflow-hidden" style={{ background: 'var(--bg-base)' }}>

        {/* ── Top bar (macOS window drag handle + app title) ────────────────────
            Full-width, 38px. Acts as the window grab region for dragging and
            macOS tiling (drag to screen edge). The left 80px is cleared via
            ::before so traffic-light buttons (⬤⬤⬤) remain clickable.      */}
        <div className="top-bar shrink-0">
          <span className="top-bar-title">2<span style={{ color: 'var(--accent)' }}>brn</span></span>
        </div>

        {/* ── Body: sidebar + content ── */}
        <div className="flex flex-1 min-h-0 overflow-hidden">

          {/* ── Sidebar ── */}
          <aside
            className="flex flex-col w-[200px] shrink-0 border-r"
            style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
          >
            {/* Nav */}
            <nav className="flex-1 flex flex-col gap-0.5 p-2 pt-3 overflow-y-auto">
              {NAV.map(item => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className="no-drag flex items-center gap-2.5 px-3 py-2 rounded-[9px] text-[14px] transition-all duration-150 select-none"
                  style={({ isActive }) => isActive
                    ? { background: 'var(--accent-glow)', color: 'var(--text)', fontWeight: 500 }
                    : { color: 'var(--text-muted)' }
                  }
                >
                  {({ isActive }) => (
                    <>
                      <span
                        className="text-[14px] w-[18px] text-center shrink-0"
                        style={{ color: isActive ? 'var(--accent)' : undefined, opacity: isActive ? 1 : 0.55 }}
                      >
                        {item.icon}
                      </span>
                      {item.label}
                    </>
                  )}
                </NavLink>
              ))}
            </nav>

            {/* Calendar toggle — only on sections where it applies */}
            {calendarApplies && (
              <div className="px-3 pb-1">
                <button
                  onClick={() => setCalendarOpen(o => !o)}
                  className="w-full text-[12px] font-mono py-1.5 rounded-[7px] transition-all duration-150 border"
                  style={calendarOpen
                    ? { background: 'var(--accent-glow)', color: 'var(--accent)', borderColor: 'rgba(129,140,248,0.35)' }
                    : { background: 'var(--bg-surface-2)', color: 'var(--text-dim)', borderColor: 'var(--border)' }
                  }
                >
                  ◈ calendar
                </button>
              </div>
            )}

            {/* Debug button */}
            <div className="px-3 pb-1">
              <button
                onClick={() => setDebugOpen(o => !o)}
                className="w-full text-[12px] font-mono py-1.5 rounded-[7px] transition-all duration-150 border"
                style={debugOpen
                  ? { background: 'var(--accent-glow)', color: 'var(--accent)', borderColor: 'rgba(129,140,248,0.35)' }
                  : { background: 'var(--bg-surface-2)', color: 'var(--text-dim)', borderColor: 'var(--border)' }
                }
              >
                ⬡ debug
              </button>
            </div>

            {/* Daemon status */}
            <div className="px-4 py-3 border-t" style={{ borderColor: 'var(--border)' }}>
              <DaemonStatus />
            </div>
          </aside>

          {/* ── Content ── */}
          <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
            <StatsBar themeMode={themeMode} onThemeModeChange={handleThemeModeChange} />
            <div className="flex flex-1 min-h-0 overflow-hidden">
              <main className="flex-1 overflow-auto">
                <Routes>
                  <Route path="/"              element={<Dashboard />} />
                  <Route path="/chat"          element={<Chat />} />
                  <Route path="/journal"       element={<Journal />} />
                  <Route path="/blog"          element={<Blog />} />
                  <Route path="/timeline"      element={<Timeline />} />
                  <Route path="/insights"      element={<Insights />} />
                  <Route path="/instructions"  element={<Instructions />} />
                  <Route path="/settings"      element={<Settings />} />
                </Routes>
              </main>
              {calendarApplies && calendarOpen && <CalendarPanel />}
              {debugOpen    && <DebugPanel    onClose={() => setDebugOpen(false)} />}
            </div>
          </div>

        </div>
      </div>
    </DateProvider>
  )
}
