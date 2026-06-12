import type { ReactNode } from 'react'

/** Screen header — display title, optional muted subtitle, right-side actions. */
export default function PageHeader({ title, subtitle, right }: {
  title: ReactNode; subtitle?: ReactNode; right?: ReactNode
}) {
  return (
    <header style={{
      display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
      gap: 'var(--space-md)', flexWrap: 'wrap', marginBottom: 'var(--space-lg)',
    }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
        <h1 style={{
          margin: 0, fontSize: 'var(--text-display)', fontWeight: 400,
          letterSpacing: 'var(--tracking-tight)', color: 'var(--fg)', lineHeight: 'var(--leading-tight)',
        }}>
          {title}
        </h1>
        {subtitle && (
          <div style={{
            fontSize: 'var(--text-base)', color: 'var(--muted)', fontWeight: 300,
            letterSpacing: 'var(--tracking-wide)',
          }}>
            {subtitle}
          </div>
        )}
      </div>
      {right && <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>{right}</div>}
    </header>
  )
}
