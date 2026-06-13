import MarkdownRenderer from '../../components/shared/MarkdownRenderer'
import { useChatSession, CHAT_CATEGORIES } from '../../hooks/useChatSession'
import { categoryChip } from '../../utils/design'

export default function Chat() {
  const { messages, input, setInput, loading, categories, toggleCategory, setCategories, send, bottomRef } = useChatSession()

  return (
    <div className="flex flex-col h-full">

      {/* Filter bar — multi-select category chips (parity with the minimal skin) */}
      <div
        className="flex items-center gap-1.5 px-5 py-2.5 border-b shrink-0 flex-wrap"
        style={{ borderColor: 'var(--border)', background: 'var(--bg-surface)' }}
      >
        <span className="text-[10px] uppercase tracking-widest self-center mr-1 font-medium" style={{ color: 'var(--text-dim)' }}>
          Category
        </span>
        {CHAT_CATEGORIES.map(cat => {
          const chip = categoryChip(cat)
          const active = categories.includes(cat)
          return (
            <button
              key={cat}
              onClick={() => toggleCategory(cat)}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium transition-all duration-100"
              style={{
                background: active ? chip.bg : 'var(--bg-surface-2)',
                color: active ? chip.text : 'var(--text-muted)',
                border: active ? `1px solid ${chip.text}40` : '1px solid var(--border)',
              }}
            >
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: chip.dot }} />
              {cat}
            </button>
          )
        })}
        {categories.length > 0 && (
          <button
            onClick={() => setCategories([])}
            className="text-[11px] px-2.5 py-1 rounded-full transition-colors"
            style={{ color: 'var(--text-dim)' }}
          >
            Clear
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="text-5xl mb-4 opacity-15">💬</div>
            <div className="text-[14px]" style={{ color: 'var(--text-dim)' }}>
              Ask anything about your past activity
            </div>
          </div>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className="max-w-[78%] rounded-[12px] px-4 py-3 text-[14px] leading-relaxed"
              style={
                msg.role === 'user'
                  ? { background: 'var(--accent-glow-2)', border: '1px solid var(--accent-glow)', color: 'var(--text)' }
                  : { background: 'var(--bg-surface)', border: '1px solid var(--border)', color: 'var(--text)' }
              }
            >
              {msg.role === 'assistant'
                ? <MarkdownRenderer content={msg.content} />
                : msg.content
              }
              {msg.streaming && (
                <span
                  className="inline-block w-1.5 h-3.5 ml-1 rounded-[2px] align-middle pulse"
                  style={{ background: 'var(--accent)' }}
                />
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form
        onSubmit={e => { e.preventDefault(); send() }}
        className="flex gap-3 px-5 py-4 border-t shrink-0"
        style={{ borderColor: 'var(--border)', background: 'var(--bg-surface)' }}
      >
        <input
          className="flex-1 rounded-[10px] border px-4 py-2.5 text-[14px] outline-none transition-shadow focus:shadow-glow-sm"
          style={{ background: 'var(--bg-input)', borderColor: 'var(--border-2)', color: 'var(--text)' }}
          placeholder="Ask your second brain…"
          value={input}
          onChange={e => setInput(e.target.value)}
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="px-5 py-2.5 rounded-[10px] text-[14px] font-medium transition-all disabled:opacity-30"
          style={{ background: 'var(--accent)', color: '#fff' }}
        >
          {loading ? '…' : '↵'}
        </button>
      </form>

    </div>
  )
}
