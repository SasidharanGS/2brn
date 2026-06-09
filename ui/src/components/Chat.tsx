import { useState, useRef, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { api } from '../api/client'
import MarkdownRenderer from './shared/MarkdownRenderer'
import { useAppDate } from '../context/DateContext'

interface Message { id: string; role: 'user' | 'assistant'; content: string; streaming?: boolean }

const CATEGORIES = ['work','research','play','learning','communication','creative','admin','other']

export default function Chat() {
  const location      = useLocation()
  const initialQuestion = (location.state as { initialQuestion?: string } | null)?.initialQuestion ?? ''
  const { selectedDate, chatDateOverridden, setChatDateOverridden } = useAppDate()
  const [messages, setMessages]             = useState<Message[]>([])
  const [input, setInput]                   = useState(initialQuestion)
  const [loading, setLoading]               = useState(false)
  const [categoryFilter, setCategoryFilter] = useState('')
  const bottomRef   = useRef<HTMLDivElement>(null)
  const hasAutoSent = useRef(false)
  const abortRef    = useRef<AbortController | null>(null)
  const streamAccRef = useRef('')
  const rafRef = useRef<number | null>(null)

  // Abort any in-flight stream on unmount
  useEffect(() => {
    return () => { abortRef.current?.abort() }
  }, [])

  // When user leaves Chat, reset the override so other sections see the real date
  useEffect(() => {
    return () => { setChatDateOverridden(false) }
  }, [setChatDateOverridden])

  // The effective date filter: empty string if user cleared it, otherwise the shared date
  const dateFilter = chatDateOverridden ? '' : selectedDate

  useEffect(() => {
    if (initialQuestion && !hasAutoSent.current) {
      hasAutoSent.current = true
      handleSend(initialQuestion)
    }
  }, []) // eslint-disable-line

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async (question: string = input) => {
    if (!question.trim() || loading) return
    setInput('')
    setLoading(true)
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    streamAccRef.current = ''
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current)

    // Target updates by the assistant message's stable id, not by array index
    // (index-based updates can hit the wrong message and are fragile).
    const assistantId = crypto.randomUUID()
    setMessages(prev => [
      ...prev,
      { id: crypto.randomUUID(), role: 'user', content: question },
      { id: assistantId, role: 'assistant', content: '', streaming: true },
    ])
    const setAssistant = (patch: Partial<Message>) =>
      setMessages(prev => prev.map(m => (m.id === assistantId ? { ...m, ...patch } : m)))
    const stopRaf = () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current)
        rafRef.current = null
      }
    }

    const scheduleFlush = () => {
      if (rafRef.current !== null) return
      rafRef.current = requestAnimationFrame(() => {
        rafRef.current = null
        setAssistant({ content: streamAccRef.current, streaming: true })
      })
    }

    try {
      for await (const chunk of api.chatStream(question, dateFilter || undefined, categoryFilter || undefined, controller.signal)) {
        streamAccRef.current += chunk
        scheduleFlush()
      }
      stopRaf()
      setAssistant({ content: streamAccRef.current, streaming: false })
    } catch (e) {
      stopRaf()
      if (e instanceof DOMException && e.name === 'AbortError') {
        // Clear the streaming cursor on the partial message instead of leaving
        // it blinking forever after the user navigates away and back.
        setAssistant({ streaming: false })
        return
      }
      setAssistant({ content: 'Something went wrong. Please try again.', streaming: false })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full">

      {/* Filter bar */}
      <div
        className="flex items-center gap-2 px-5 py-2.5 border-b shrink-0 flex-wrap"
        style={{ borderColor: 'var(--border)', background: 'var(--bg-surface)' }}
      >
        <select
          value={categoryFilter}
          onChange={e => setCategoryFilter(e.target.value)}
          className="rounded-[7px] px-2.5 py-1.5 text-[12px] border outline-none"
          style={{ background: 'var(--bg-input)', borderColor: 'var(--border-2)', color: 'var(--text)' }}
        >
          <option value="">All categories</option>
          {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        {categoryFilter && (
          <button
            onClick={() => setCategoryFilter('')}
            className="text-[12px] px-2.5 py-1 rounded-[7px] transition-colors"
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
        onSubmit={e => { e.preventDefault(); handleSend() }}
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
