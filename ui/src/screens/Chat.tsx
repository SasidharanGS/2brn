import type { CSSProperties } from 'react'
import { useChatSession, CHAT_CATEGORIES, SUGGESTED_PROMPTS } from '../hooks/useChatSession'
import { SectionLabel, CategoryChip, ChatMessage, PromptPill, ChatComposer, Icon, useKit } from '../ui-kit'

// Unified Chat — one component for both skins. Streaming/state lives in
// useChatSession; the chrome is token-driven CSS, and the genuinely-divergent
// pieces (message bubble vs labelled block, colour vs monochrome chips, joined
// vs bordered composer) are ui-kit leaves that branch on skin.
function ChatEmptyIcon() {
  const { skin } = useKit()
  if (skin === 'minimal') {
    return <span style={{ color: 'var(--k-muted)', opacity: 0.5 }}><Icon name="chat" size={34} strokeWidth={1.2} /></span>
  }
  return <span aria-hidden="true" style={{ fontSize: 48, opacity: 0.15 }}>💬</span>
}

export default function Chat() {
  const { messages, input, setInput, loading, categories, toggleCategory, setCategories, send, bottomRef } = useChatSession()

  return (
    <div className="k-chat">
      <div className="k-chat-filter">
        <SectionLabel style={{ marginRight: 'var(--k-space-xs)' }}>Filter</SectionLabel>
        <CategoryChip label="all categories" active={categories.length === 0} onClick={() => setCategories([])} />
        {CHAT_CATEGORIES.map(c => (
          <CategoryChip key={c} label={c} cat={c} active={categories.includes(c)} onClick={() => toggleCategory(c)} />
        ))}
      </div>

      <div className="k-chat-scroll">
        {messages.length === 0 ? (
          <div style={{
            height: '100%', minHeight: 320, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 'var(--k-space-md)', textAlign: 'center',
          }}>
            <ChatEmptyIcon />
            <div style={{
              fontSize: 'var(--k-text-lg)', color: 'var(--k-dim)',
              textTransform: 'var(--k-text-transform)' as CSSProperties['textTransform'],
            }}>
              Ask anything about your past activity
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--k-space-xs)', justifyContent: 'center', maxWidth: 460 }}>
              {SUGGESTED_PROMPTS.map(p => <PromptPill key={p} onClick={() => send(p)}>{p}</PromptPill>)}
            </div>
          </div>
        ) : (
          <div className="k-chat-msgs">
            {messages.map(m => <ChatMessage key={m.id} msg={m} />)}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <ChatComposer value={input} onChange={setInput} onSubmit={() => send()} loading={loading} />
    </div>
  )
}
