import { createContext, useContext, useState, useCallback } from 'react'

// Use local date components — NOT .toISOString() which converts to UTC
// and causes off-by-one in timezones ahead of UTC (e.g. IST UTC+5:30)
function toDateStr(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

interface DateContextValue {
  selectedDate: string                  // YYYY-MM-DD — shared across all sections
  setSelectedDate: (d: string) => void
  clearDate: () => void                 // reset to today
  // Chat-only override: when true, chat searches all history (no date restriction)
  // Resets to false whenever the user leaves Chat so other sections are unaffected
  chatDateOverridden: boolean
  setChatDateOverridden: (v: boolean) => void
}

const DateContext = createContext<DateContextValue | null>(null)

export function DateProvider({ children }: { children: React.ReactNode }) {
  const [selectedDate, setSelectedDateRaw]     = useState(toDateStr(new Date()))
  const [chatDateOverridden, setChatDateOverridden] = useState(false)

  const setSelectedDate = useCallback((d: string) => {
    setSelectedDateRaw(d)
  }, [])

  const clearDate = useCallback(() => {
    setSelectedDateRaw(toDateStr(new Date()))
  }, [])

  return (
    <DateContext.Provider value={{
      selectedDate, setSelectedDate, clearDate,
      chatDateOverridden, setChatDateOverridden,
    }}>
      {children}
    </DateContext.Provider>
  )
}

export function useAppDate() {
  const ctx = useContext(DateContext)
  if (!ctx) throw new Error('useAppDate must be used inside DateProvider')
  return ctx
}

export { toDateStr }
