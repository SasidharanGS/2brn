import type { CSSProperties, ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
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

/** Screen header — title (cased per skin), optional subtitle, right-side actions. */
export function PageHeader({ title, subtitle, right }: {
  title: ReactNode; subtitle?: ReactNode; right?: ReactNode
}) {
  return (
    <header style={{
      display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
      gap: 'var(--k-space-md)', flexWrap: 'wrap', marginBottom: 'var(--k-space-lg)',
    }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--k-space-xs)' }}>
        <h1 style={{
          margin: 0, color: 'var(--k-fg)', fontFamily: 'var(--k-font)',
          fontSize: 'var(--k-text-heading)', fontWeight: 'var(--k-heading-weight)' as CSSProperties['fontWeight'],
          letterSpacing: 'var(--k-tracking-tight)', lineHeight: 1.2,
          textTransform: 'var(--k-text-transform)' as CSSProperties['textTransform'],
        }}>
          {title}
        </h1>
        {subtitle && (
          <div style={{
            fontSize: 'var(--k-text-body)', color: 'var(--k-muted)',
            fontWeight: 'var(--k-body-weight)' as CSSProperties['fontWeight'],
            textTransform: 'var(--k-text-transform)' as CSSProperties['textTransform'],
          }}>
            {subtitle}
          </div>
        )}
      </div>
      {right && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--k-space-sm)', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          {right}
        </div>
      )}
    </header>
  )
}

/** Small status pill (e.g. "edited"). */
export function Badge({ children }: { children: ReactNode }) {
  return (
    <span style={{
      display: 'inline-block', background: 'var(--k-badge-bg)', color: 'var(--k-badge-fg)',
      borderRadius: 'var(--k-radius-pill)', padding: '2px 8px',
      fontSize: 'var(--k-text-label)', fontWeight: 'var(--k-label-weight)' as CSSProperties['fontWeight'],
      textTransform: 'var(--k-text-transform)' as CSSProperties['textTransform'], whiteSpace: 'nowrap',
    }}>
      {children}
    </span>
  )
}

export type ButtonVariant = 'ghost' | 'primary' | 'danger'

/** Action button. `primary` = filled accent (modern) / accent-on-hover (minimal). */
export function Button({ children, onClick, disabled, variant = 'ghost', type = 'button' }: {
  children: ReactNode; onClick?: () => void; disabled?: boolean
  variant?: ButtonVariant; type?: 'button' | 'submit'
}) {
  return (
    <button type={type} onClick={onClick} disabled={disabled} className={`k-btn k-btn--${variant}`}>
      {children}
    </button>
  )
}

/** Bordered reading card for generated documents, with an optional action footer. */
export function ReadingCard({ children, footer }: { children: ReactNode; footer?: ReactNode }) {
  return (
    <article style={{
      border: '1px solid var(--k-rule)', borderRadius: 'var(--k-radius)',
      background: 'var(--k-surface)', padding: 'var(--k-card-pad)',
    }}>
      {children}
      {footer && (
        <div style={{
          borderTop: '1px solid var(--k-rule)', marginTop: 'var(--k-space-lg)',
          paddingTop: 'var(--k-space-md)', display: 'flex', gap: 'var(--k-space-sm)', flexWrap: 'wrap',
        }}>
          {footer}
        </div>
      )}
    </article>
  )
}

/** Large empty/error state — icon follows the skin (emoji / line-SVG). */
export function EmptyState({ icon, title, children, dashed }: {
  icon?: IconName; title?: ReactNode; children?: ReactNode; dashed?: boolean
}) {
  const { skin } = useKit()
  const boxed = skin === 'modern' && !dashed
  return (
    <div style={{
      border: dashed ? '1px dashed var(--k-rule)' : boxed ? '1px solid var(--k-rule)' : 'none',
      borderRadius: 'var(--k-radius)', background: boxed ? 'var(--k-surface)' : 'transparent',
      padding: 'var(--k-empty-pad)', textAlign: 'center', display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', gap: 'var(--k-space-md)', minHeight: 280,
    }}>
      {icon && <EmptyIcon name={icon} />}
      {title && (
        <div style={{
          fontSize: skin === 'minimal' ? 'var(--k-text-lg)' : 'var(--k-text-body)',
          color: skin === 'minimal' ? 'var(--k-fg)' : 'var(--k-muted)',
          fontWeight: 'var(--k-body-weight)' as CSSProperties['fontWeight'],
          textTransform: 'var(--k-text-transform)' as CSSProperties['textTransform'],
        }}>
          {title}
        </div>
      )}
      {children && (
        <div style={{
          fontSize: 'var(--k-text-body)', color: 'var(--k-muted)', maxWidth: 440, lineHeight: 1.6,
          fontWeight: 'var(--k-body-weight)' as CSSProperties['fontWeight'],
          textTransform: 'var(--k-text-transform)' as CSSProperties['textTransform'],
        }}>
          {children}
        </div>
      )}
    </div>
  )
}

function EmptyIcon({ name }: { name: IconName }) {
  const { skin } = useKit()
  if (skin === 'minimal') {
    return <span style={{ color: 'var(--k-muted)', opacity: 0.6 }}><Icon name={name} size={28} strokeWidth={1.2} /></span>
  }
  const emoji = ICON_EMOJI[name]
  return emoji
    ? <span aria-hidden="true" style={{ fontSize: 36, lineHeight: 1, opacity: 0.2 }}>{emoji}</span>
    : <Icon name={name} size={28} />
}

const SAFE_URL_RE = /^(https?:|mailto:|\/|#)/i

/** Markdown body. Modern uses the simple `.k-prose` style; minimal uses the
 *  elaborate per-variant `.m-prose` reading style (a genuine per-skin leaf). */
export function Markdown({ content, variant }: { content: string; variant: 'journal' | 'blog' | 'chat' }) {
  const { skin } = useKit()
  const className = skin === 'minimal' ? `m-prose m-prose--${variant}` : 'k-prose'
  return (
    <div className={className}>
      <ReactMarkdown urlTransform={url => (SAFE_URL_RE.test(url) ? url : '')}>
        {content}
      </ReactMarkdown>
    </div>
  )
}

/** Monospace editing textarea (journal/blog edit mode). */
export function TextArea({ value, onChange, rows = 22 }: {
  value: string; onChange: (v: string) => void; rows?: number
}) {
  return (
    <textarea
      value={value}
      onChange={e => onChange(e.target.value)}
      rows={rows}
      style={{
        width: '100%', boxSizing: 'border-box', resize: 'vertical',
        background: 'var(--k-surface)', border: '1px solid var(--k-rule-strong)',
        borderRadius: 'var(--k-radius)', padding: 'var(--k-space-md)',
        color: 'var(--k-fg)', fontFamily: 'var(--k-font-mono)', fontSize: 'var(--k-text-body)',
        fontWeight: 'var(--k-body-weight)' as CSSProperties['fontWeight'], lineHeight: 1.7, outline: 'none',
      }}
    />
  )
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
