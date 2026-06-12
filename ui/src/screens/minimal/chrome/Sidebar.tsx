import { NavLink } from 'react-router-dom'
import { ROUTES } from '../../../theme/routes'
import { useDaemonStatus } from '../../../hooks/useDaemonStatus'
import Icon, { type IconName } from '../Icon'

// Fixed left rail (180px, 1px right rule): wordmark, 9-item lowercase nav,
// calendar/debug toggles, live capturing footer (mono + accent dot).

function RailButton({ icon, label, active, onClick }: {
  icon: IconName; label: string; active: boolean; onClick: () => void
}) {
  return (
    <button
      type="button" onClick={onClick}
      className={`m-rail-btn${active ? ' active' : ''}`}
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7,
        width: '100%', background: 'none', padding: '7px 0', cursor: 'pointer',
        fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-wide)',
        fontWeight: 300, fontFamily: 'var(--font-sans)',
      }}
    >
      <Icon name={icon} size={13} />{label}
    </button>
  )
}

interface Props {
  calendarApplies: boolean
  calendarOpen: boolean
  onToggleCalendar: () => void
  debugOpen: boolean
  onToggleDebug: () => void
}

export default function Sidebar({ calendarApplies, calendarOpen, onToggleCalendar, debugOpen, onToggleDebug }: Props) {
  const status = useDaemonStatus()
  const capturing = status?.status === 'capturing'

  return (
    <aside
      className="m-sidebar"
      style={{
        width: 'var(--sidebar-w)', flex: '0 0 auto', height: '100%',
        padding: 'var(--space-md) var(--space-md) var(--space-sm)',
        display: 'flex', flexDirection: 'column', boxSizing: 'border-box',
        borderRight: '1px solid var(--rule)',
      }}
    >
      <div
        className="m-wordmark"
        style={{
          fontSize: 'var(--text-xl)', fontWeight: 400, letterSpacing: 'var(--tracking-name)',
          color: 'var(--fg)', padding: 'var(--space-xs) 0 var(--space-md)',
        }}
      >
        2<span style={{ color: 'var(--accent)' }}>brn</span>
      </div>

      <nav style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        {ROUTES.map(({ to, screen, end }) => (
          <NavLink
            key={to} to={to} end={end}
            className={({ isActive }) => `m-nav-link${isActive ? ' active' : ''}`}
            style={{
              display: 'flex', alignItems: 'center', gap: 'var(--space-sm)',
              padding: '5px 0', textDecoration: 'none',
              fontSize: 'var(--text-sm)', letterSpacing: 'var(--tracking-wide)',
              fontFamily: 'var(--font-sans)',
            }}
          >
            {({ isActive }) => (
              <>
                <Icon name={screen as IconName} size={15} strokeWidth={isActive ? 1.7 : 1.5} />
                {screen}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
        {calendarApplies && (
          <RailButton icon="calendar" label="calendar" active={calendarOpen} onClick={onToggleCalendar} />
        )}
        <RailButton icon="dot" label="debug" active={debugOpen} onClick={onToggleDebug} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 'var(--space-sm)' }}>
          <span style={{
            width: 6, height: 6, borderRadius: '50%', flex: '0 0 auto',
            background: capturing ? 'var(--accent)' : 'var(--muted)',
          }} />
          <span style={{
            fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-wide)',
            color: 'var(--muted)', fontWeight: 300, fontFamily: 'var(--font-mono)',
          }}>
            {status ? `${status.status} · ${status.capture_count_today}` : 'offline'}
          </span>
        </div>
      </div>
    </aside>
  )
}
