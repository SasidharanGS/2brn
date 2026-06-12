import type { CSSProperties, ReactNode } from 'react'
import { inkVar } from './minimalDesign'

// 2brn minimal-skin primitives, ported from the design handoff prototype.
// Two-color palette, Inter 300/400, 1px rules, no shadows, no radius beyond
// the 3px pill. Hover transitions live in theme/minimal.css (.m-ghost etc.).

/** Section micro-label — tiny, wide-tracked, muted. */
export function Label({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return (
    <div style={{
      fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-label)',
      color: 'var(--muted)', fontWeight: 300, margin: 0, ...style,
    }}>
      {children}
    </div>
  )
}

/** State label with its intensity square — the monochrome state encoding. */
export function StateLabel({ state, level }: { state: string; level: number }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-wide)',
      color: 'var(--muted)', fontWeight: 300, whiteSpace: 'nowrap',
    }}>
      <span aria-hidden="true" style={{ width: 7, height: 7, background: inkVar(level), flex: '0 0 auto' }} />
      {state}
    </span>
  )
}

/** Neutral tag pill — the category encoding (no hue). */
export function Pill({ children }: { children: ReactNode }) {
  return (
    <span style={{
      display: 'inline-block', background: 'var(--pill-bg)', color: 'var(--muted)',
      borderRadius: 'var(--radius-pill)', padding: '2px 7px',
      fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-snug)',
      fontWeight: 300, whiteSpace: 'nowrap',
    }}>
      {children}
    </span>
  )
}

/** Bordered card — 1px rule, no elevation. */
export function Card({ label, children, style, action }: {
  label?: ReactNode; children: ReactNode; style?: CSSProperties; action?: ReactNode
}) {
  return (
    <section style={{
      border: '1px solid var(--rule)', padding: 'var(--space-md)',
      display: 'flex', flexDirection: 'column', gap: 'var(--space-md)', ...style,
    }}>
      {(label || action) && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--space-sm)' }}>
          {label && <Label>{label}</Label>}
          {action}
        </div>
      )}
      {children}
    </section>
  )
}

/** Quiet bordered button (edit, regenerate, + add). Hover via .m-ghost CSS. */
export function GhostButton({ children, onClick, accent, disabled, type = 'button' }: {
  children: ReactNode; onClick?: () => void; accent?: boolean; disabled?: boolean
  type?: 'button' | 'submit'
}) {
  return (
    <button
      type={type} onClick={onClick} disabled={disabled}
      className={`m-ghost${accent ? ' accent' : ''}`}
      style={{
        background: 'none', padding: '6px 12px', cursor: disabled ? 'default' : 'pointer',
        fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-wide)', fontWeight: 300,
        fontFamily: 'var(--font-sans)', display: 'inline-flex', alignItems: 'center', gap: 6,
        opacity: disabled ? 0.5 : 1,
      }}
    >
      {children}
    </button>
  )
}

/** Segmented control (day/week/month…). Active segment = fg block / bg text. */
export function Segmented<T extends string>({ value, options, onChange }: {
  value: T; options: readonly T[]; onChange: (v: T) => void
}) {
  return (
    <div style={{ display: 'inline-flex', border: '1px solid var(--rule)', padding: 2 }}>
      {options.map(o => {
        const active = o === value
        return (
          <button
            key={o} type="button" onClick={() => onChange(o)}
            style={{
              background: active ? 'var(--fg)' : 'none',
              color: active ? 'var(--bg)' : 'var(--muted)',
              border: 'none', padding: '4px 12px', cursor: 'pointer',
              fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-wide)',
              fontWeight: 300, fontFamily: 'var(--font-sans)', transition: 'color 0.2s ease',
            }}
          >
            {o}
          </button>
        )
      })}
    </div>
  )
}

/** Centered empty state (instructions, plugins, chat). */
export function EmptyState({ icon, title, children, dashed }: {
  icon?: ReactNode; title?: ReactNode; children?: ReactNode; dashed?: boolean
}) {
  return (
    <div style={{
      border: dashed ? '1px dashed var(--rule)' : 'none',
      padding: 'var(--space-xl) var(--space-lg)',
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      gap: 'var(--space-md)', textAlign: 'center', minHeight: 320,
    }}>
      {icon && <span style={{ color: 'var(--muted)', opacity: 0.6 }}>{icon}</span>}
      {title && <div style={{ fontSize: 'var(--text-lg)', color: 'var(--fg)', fontWeight: 300 }}>{title}</div>}
      {children && (
        <div style={{
          fontSize: 'var(--text-base)', color: 'var(--muted)', fontWeight: 300,
          lineHeight: 'var(--leading-normal)', maxWidth: 440,
        }}>
          {children}
        </div>
      )}
    </div>
  )
}

/** Form field wrapper — label above, optional hint below. */
export function Field({ label, hint, children }: { label: ReactNode; hint?: ReactNode; children: ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
      <Label>{label}</Label>
      {children}
      {hint && (
        <div style={{
          fontSize: 'var(--text-2xs)', color: 'var(--muted)', fontWeight: 300,
          letterSpacing: 'var(--tracking-wide)', lineHeight: 'var(--leading-snug)',
        }}>
          {hint}
        </div>
      )}
    </div>
  )
}

/** Borderless input style — bottom rule only (settings inputs). */
export const lineInput: CSSProperties = {
  background: 'none', border: 'none', borderBottom: '1px solid var(--rule)',
  padding: '6px 0', color: 'var(--fg)', fontSize: 'var(--text-base)',
  fontWeight: 300, fontFamily: 'var(--font-sans)', outline: 'none', width: '100%',
}

/** Minimal switch — on = --ink-3 track, square-ish, controlled. */
export function Switch({ on, onToggle, disabled }: { on: boolean; onToggle: () => void; disabled?: boolean }) {
  return (
    <button
      type="button" onClick={onToggle} aria-pressed={on} disabled={disabled}
      style={{
        width: 34, height: 18, borderRadius: 9, border: '1px solid var(--rule)',
        background: on ? 'var(--ink-3)' : 'var(--bg)', position: 'relative',
        cursor: disabled ? 'default' : 'pointer', transition: 'background 0.2s ease',
        flex: '0 0 auto', padding: 0, opacity: disabled ? 0.5 : 1,
      }}
    >
      <span style={{
        position: 'absolute', top: 2, left: on ? 17 : 2, width: 12, height: 12,
        borderRadius: '50%', background: on ? 'var(--bg)' : 'var(--fg)', transition: 'left 0.2s ease',
      }} />
    </button>
  )
}
