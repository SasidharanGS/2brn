import type { ReactNode } from 'react'

/** Bordered reading card for generated documents (journal/blog). */
export default function DocCard({ children, footer }: { children: ReactNode; footer?: ReactNode }) {
  return (
    <article style={{ border: '1px solid var(--rule)', padding: 'var(--space-lg)', maxWidth: 760 }}>
      {children}
      {footer && (
        <div style={{
          borderTop: '1px solid var(--rule)', marginTop: 'var(--space-lg)',
          paddingTop: 'var(--space-md)', display: 'flex', gap: 'var(--space-sm)',
        }}>
          {footer}
        </div>
      )}
    </article>
  )
}
