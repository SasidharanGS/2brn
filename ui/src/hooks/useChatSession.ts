import { useState, useRef, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { api } from '../api/client'
import { useAppDate } from '../context/DateContext'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
}

export const CHAT_CATEGORIES = ['work','research','play','learning','communication','creative','admin','other']

/** Chat data + streaming logic, shared by every skin's Chat presentation. */
export function useChatSession() {
  const location = useLocation()
  const initialQuestion = (location.state as { initialQuestion?: string } | null)?.initialQuestion ?? ''
  const { selectedDate, chatDateOverridden, setChatDateOverridden } = useAppDate()
  const [messages, setMessages]             = useState<ChatMessage[]>([])
  const [input, setInput]                   = useState(initialQuestion)
  const [loading, setLoading]               = useState(false)
  const [categories, setCategories]         = useState<string[]>([])
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

  const toggleCategory = (c: string) =>
    setCategories(prev => (prev.includes(c) ? prev.filter(x => x !== c) : [...prev, c]))

  useEffect(() => {
    if (initialQuestion && !hasAutoSent.current) {
      hasAutoSent.current = true
      send(initialQuestion)
    }
  }, []) // eslint-disable-line

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async (question: string = input) => {
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
    const setAssistant = (patch: Partial<ChatMessage>) =>
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
      for await (const chunk of api.chatStream(question, dateFilter || undefined, categories.length ? categories : undefined, controller.signal)) {
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

  return { messages, input, setInput, loading, categories, setCategories, toggleCategory, send, bottomRef }
}
