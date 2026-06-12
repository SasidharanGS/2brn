import { useEffect } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import ErrorBoundary from './components/shared/ErrorBoundary'
import { DateProvider } from './context/DateContext'
import { useTheme } from './theme/ThemeContext'
import { getScreen, getShell } from './theme/registry'
import { ROUTES } from './theme/routes'

export default function App() {
  const location = useLocation()
  const { skin } = useTheme()

  useEffect(() => {
    window.electronAPI.getPlatform().then(platform => {
      document.documentElement.classList.toggle('macos', platform === 'darwin')
    })
  }, [])

  const calendarApplies =
    ROUTES.find(r => r.to === location.pathname || (r.end && location.pathname === '/'))?.hasCalendar ?? false
  const Shell = getShell(skin)

  return (
    <DateProvider>
      <Shell calendarApplies={calendarApplies}>
        <ErrorBoundary>
          <Routes>
            {ROUTES.map(({ to, screen }) => {
              const Screen = getScreen(skin, screen)
              return <Route key={to} path={to} element={<Screen />} />
            })}
          </Routes>
        </ErrorBoundary>
      </Shell>
    </DateProvider>
  )
}
