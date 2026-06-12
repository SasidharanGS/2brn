import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'

/** Send a question to the Chat screen (used by the home ask box). */
export function useAskNavigation() {
  const navigate = useNavigate()
  return useCallback((question: string) => {
    if (!question.trim()) return
    navigate('/chat', { state: { initialQuestion: question } })
  }, [navigate])
}
