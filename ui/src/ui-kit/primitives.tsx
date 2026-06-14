import type { CSSProperties, ReactNode } from 'react'
import { useKit } from './KitProvider'
import Icon, { ICON_EMOJI, type IconName } from './Icon'

// Shared presentation primitives. Each renders ONE markup tree for both skins;
// all skin variation comes from the `--k-*` token contract (theme/tokens.css)
// plus a handful of structural branches on `useKit().skin` where the designs
// genuinely diverge (e.g. emoji vs SVG icons).

export type { IconName }
export { Icon }

/** Centered (modern) / left-aligned (minimal) page container with skin padding. */
export function Page({ children, max, enter = true, style }: {
  children: ReactNode; max?: number | string; enter?: boolean; style?: CSSProperties
}) {
  const { skin } = useKit()
  return (
    <div
      className={skin === 'modern' && enter ? 'page-enter' : undefined}
      style={{ padding: 'var(--k-page-pad)', ...style }}
    >
      <div style={{ maxWidth: max ?? 'var(--k-page-max)', margin: '0 var(--k-page-align)' }}>
        {children}
      </div>
    </div>
  )
}

/** Page title (h1). */
export function Heading({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return (
    <h1 style={{
      margin: 0, color: 'var(--k-fg)', fontFamily: 'var(--k-font)',
      fontSize: 'var(--k-text-hero)', fontWeight: 'var(--k-heading-weight)' as CSSProperties['fontWeight'],
      letterSpacing: 'var(--k-tracking-tight)', lineHeight: 1.2,
      textTransform: 'var(--k-text-transform)' as CSSProperties['textTransform'], ...style,
    }}>
      {children}
    </h1>
  )
}

/** Dim secondary line under a heading (dates, counts). */
export function Caption({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return (
    <div style={{
      color: 'var(--k-dim)', fontSize: 'var(--k-text-sm)',
      fontWeight: 'var(--k-body-weight)' as CSSProperties['fontWeight'],
      textTransform: 'var(--k-text-transform)' as CSSProperties['textTransform'], ...style,
    }}>
      {children}
    </div>
  )
}

/** Tiny tracked section micro-label (UPPERCASE in modern, lowercase in minimal). */
export function SectionLabel({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return (
    <div style={{
      color: 'var(--k-dim)', fontSize: 'var(--k-text-label)',
      fontWeight: 'var(--k-label-weight)' as CSSProperties['fontWeight'],
      letterSpacing: 'var(--k-label-tracking)',
      textTransform: 'var(--k-label-transform)' as CSSProperties['textTransform'], ...style,
    }}>
      {children}
    </div>
  )
}

/** Ask/search row — controlled input + submit button. Submits on Enter or click. */
export function AskBox({ value, onChange, onSubmit, placeholder, submitLabel = 'Ask' }: {
  value: string
  onChange: (v: string) => void
  onSubmit: () => void
  placeholder?: string
  submitLabel?: string
}) {
  return (
    <form
      className="k-askbox"
      onSubmit={e => { e.preventDefault(); onSubmit() }}
    >
      <input
        className="k-askbox-input"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        style={{
          padding: 'var(--k-space-sm) var(--k-space-md)',
          fontSize: 'var(--k-text-body)',
          fontWeight: 'var(--k-body-weight)' as CSSProperties['fontWeight'],
        }}
      />
      <button
        type="submit"
        className="k-askbox-btn"
        disabled={!value.trim()}
        style={{
          padding: 'var(--k-space-sm) var(--k-space-lg)',
          fontSize: 'var(--k-text-sm)',
          fontWeight: 'var(--k-emphasis-weight)' as CSSProperties['fontWeight'],
          textTransform: 'var(--k-text-transform)' as CSSProperties['textTransform'],
        }}
      >
        {submitLabel}
      </button>
    </form>
  )
}

/** Icon that follows the skin: emoji in modern, line-SVG in minimal. */
export function TileIcon({ name, size = 16 }: { name: IconName; size?: number }) {
  const { skin } = useKit()
  if (skin === 'minimal') return <Icon name={name} size={size} />
  const emoji = ICON_EMOJI[name]
  return emoji
    ? <span aria-hidden="true" style={{ fontSize: size, lineHeight: 1 }}>{emoji}</span>
    : <Icon name={name} size={size} />
}

/** Navigation tile — icon + title + description, used by Home. */
export function NavTile({ icon, title, desc, onClick }: {
  icon: IconName; title: string; desc: string; onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="k-navtile"
      style={{
        padding: 'var(--k-space-md)', display: 'flex', flexDirection: 'column',
        gap: 'var(--k-space-2xs)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--k-space-sm)', color: 'var(--k-fg)' }}>
        <TileIcon name={icon} />
        <span style={{
          fontSize: 'var(--k-text-title)', color: 'var(--k-fg)',
          fontWeight: 'var(--k-emphasis-weight)' as CSSProperties['fontWeight'],
          textTransform: 'var(--k-text-transform)' as CSSProperties['textTransform'],
        }}>
          {title}
        </span>
      </div>
      <span style={{
        fontSize: 'var(--k-text-meta)', color: 'var(--k-muted)',
        fontWeight: 'var(--k-body-weight)' as CSSProperties['fontWeight'],
        textTransform: 'var(--k-text-transform)' as CSSProperties['textTransform'],
      }}>
        {desc}
      </span>
    </button>
  )
}
