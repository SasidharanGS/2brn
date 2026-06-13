import { useChatSession, CHAT_CATEGORIES } from '../../hooks/useChatSession'
import Icon from './Icon'
import Prose from './Prose'
import { Label } from './primitives'

const SUGGESTED_PROMPTS = [
  'what did i work on this morning?',
  'how focused was i today?',
  'summarise my day so far',
]

/** Multi-select category chip — accent fill + × when selected. Background is
    intentionally NOT transitioned so the selection snaps instantly. */
function CatPill({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button" onClick={onClick}
      onMouseEnter={e => { if (!active) { e.currentTarget.style.color = 'var(--fg)'; e.currentTarget.style.borderColor = 'var(--muted)' } }}
      onMouseLeave={e => { if (!active) { e.currentTarget.style.color = 'var(--muted)'; e.currentTarget.style.borderColor = 'var(--rule)' } }}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        background: active ? 'var(--accent)' : 'none',
        color: active ? 'var(--bg)' : 'var(--muted)',
        border: `1px solid ${active ? 'var(--accent)' : 'var(--rule)'}`,
        borderRadius: 'var(--radius-pill)', padding: '4px 11px', cursor: 'pointer',
        fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-snug)',
        fontWeight: active ? 400 : 300, fontFamily: 'var(--font-sans)',
        transition: 'color 0.18s ease, border-color 0.18s ease',
      }}
    >
      {label}
      {active && <span aria-hidden="true" style={{ fontSize: 'var(--text-xs)', lineHeight: 1, opacity: 0.85 }}>×</span>}
    </button>
  )
}

export default function Chat() {
  const { messages, input, setInput, loading, categories, setCategories, toggleCategory, send, bottomRef } = useChatSession()

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%',
      padding: 'var(--space-lg)', boxSizing: 'border-box',
    }}>
      {/* Category filter — multi-select pills */}
      <div style={{
        display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-xs)',
        paddingBottom: 'var(--space-md)', borderBottom: '1px solid var(--rule)', flex: '0 0 auto',
      }}>
        <Label style={{ marginRight: 'var(--space-xs)' }}>filter</Label>
        <CatPill label="all categories" active={categories.length === 0} onClick={() => setCategories([])} />
        {CHAT_CATEGORIES.map(c => (
          <CatPill key={c} label={c} active={categories.includes(c)} onClick={() => toggleCategory(c)} />
        ))}
      </div>

      {/* Message stream */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 'var(--space-lg) 0', minHeight: 0 }}>
        {messages.length === 0 ? (
          <div style={{
            height: '100%', minHeight: 320, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 'var(--space-md)',
          }}>
            <span style={{ color: 'var(--muted)', opacity: 0.5 }}>
              <Icon name="chat" size={34} strokeWidth={1.2} />
            </span>
            <div style={{ fontSize: 'var(--text-lg)', color: 'var(--muted)', fontWeight: 300 }}>
              ask anything about your past activity
            </div>
            <div style={{
              display: 'flex', flexWrap: 'wrap', gap: 'var(--space-xs)',
              justifyContent: 'center', maxWidth: 'var(--measure)',
            }}>
              {SUGGESTED_PROMPTS.map(p => (
                <button
                  key={p} type="button" onClick={() => send(p)} className="m-pill-btn"
                  style={{
                    padding: '5px 11px', cursor: 'pointer',
                    fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-snug)',
                    fontWeight: 300, fontFamily: 'var(--font-sans)',
                  }}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div style={{
            maxWidth: 'var(--measure)', margin: '0 auto',
            display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)',
          }}>
            {messages.map(msg => (
              <div key={msg.id} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
                <Label>{msg.role === 'user' ? 'you' : '2brn'}</Label>
                {msg.role === 'assistant' ? (
                  msg.streaming && !msg.content ? (
                    <p style={{ margin: 0, fontSize: 'var(--text-lg)', color: 'var(--muted)', fontWeight: 300 }}>…</p>
                  ) : (
                    <Prose content={msg.content} variant="chat" />
                  )
                ) : (
                  <p style={{
                    margin: 0, fontSize: 'var(--text-lg)', lineHeight: 'var(--leading-loose)',
                    fontWeight: 300, color: 'var(--fg)', whiteSpace: 'pre-wrap',
                  }}>
                    {msg.content}
                  </p>
                )}
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Composer */}
      <form
        onSubmit={e => { e.preventDefault(); send() }}
        style={{ display: 'flex', gap: 0, border: '1px solid var(--rule)', flex: '0 0 auto' }}
      >
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          disabled={loading}
          placeholder="ask your second brain…"
          style={{
            flex: 1, background: 'none', border: 'none', outline: 'none',
            padding: 'var(--space-sm) var(--space-md)', color: 'var(--fg)',
            fontSize: 'var(--text-base)', fontWeight: 300, fontFamily: 'var(--font-sans)',
          }}
        />
        <button
          type="submit" aria-label="send" disabled={loading || !input.trim()} className="m-fill-btn"
          style={{
            border: 'none', borderLeft: '1px solid var(--rule)', padding: '0 var(--space-md)',
            cursor: 'pointer', display: 'flex', alignItems: 'center',
            opacity: loading || !input.trim() ? 0.5 : 1,
          }}
        >
          <Icon name="send" size={16} />
        </button>
      </form>
    </div>
  )
}
