import type { ReactNode } from 'react'
import { useTheme, type ThemeMode } from '../../../theme/ThemeContext'
import { useTopBarStats } from '../../../hooks/useTopBarStats'
import Icon, { type IconName } from '../Icon'

// 52px status strip: now · top · focused% on the left, theme control right.
// The live "now" dot is the one accent — a live, important cue.

const THEME_SEGMENTS: { mode: ThemeMode; icon: IconName }[] = [
  { mode: 'light', icon: 'sun' },
  { mode: 'system', icon: 'monitor' },
  { mode: 'dark', icon: 'moon' },
]

function ThemeControl() {
  const { mode, setMode } = useTheme()
  return (
    <div style={{ display: 'inline-flex', border: '1px solid var(--rule)', padding: 2 }}>
      {THEME_SEGMENTS.map(({ mode: m, icon }) => {
        const active = mode === m
        return (
          <button
            key={m} type="button" onClick={() => setMode(m)} title={m}
            style={{
              background: active ? 'var(--fg)' : 'none',
              color: active ? 'var(--bg)' : 'var(--muted)',
              border: 'none', padding: '5px 9px', cursor: 'pointer',
              display: 'flex', alignItems: 'center', transition: 'color 0.2s ease',
            }}
          >
            <Icon name={icon} size={15} />
          </button>
        )
      })}
    </div>
  )
}

function StatusItem({ label, value, live }: { label: string; value: ReactNode; live?: boolean }) {
  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
      <span style={{
        fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-wide)',
        color: 'var(--muted)', fontWeight: 300,
      }}>
        {label}
      </span>
      {live && <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent)', flex: '0 0 auto' }} />}
      <span style={{
        fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-snug)',
        color: 'var(--fg)', fontWeight: 400,
      }}>
        {value}
      </span>
    </div>
  )
}

const sep = <span style={{ width: 1, height: 14, background: 'var(--rule)' }} />

export default function TopBar() {
  const { topState, topCategory, focusPct } = useTopBarStats()
  return (
    <header
      className="m-topbar"
      style={{
        height: 'var(--topbar-h)', borderBottom: '1px solid var(--rule)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 var(--space-md)', gap: 'var(--space-md)', flex: '0 0 auto',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)' }}>
        <StatusItem label="now" value={topState ?? '—'} live />
        {sep}
        <StatusItem label="top" value={topCategory ?? '—'} />
        {sep}
        <StatusItem label="focused" value={`${focusPct}%`} />
      </div>
      <ThemeControl />
    </header>
  )
}
