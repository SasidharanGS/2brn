import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { queryKeys } from '../api/queryKeys'
import { useAppDate } from '../context/DateContext'

/** Journal entry data, edit state, and schedule control for the selected date. */
export function useJournalEntry() {
  const { selectedDate } = useAppDate()
  const [editing, setEditing]                 = useState(false)
  const [editContent, setEditContent]         = useState('')
  const [scheduleEditing, setScheduleEditing] = useState(false)
  const [scheduleTime, setScheduleTime]       = useState('21:00')
  const qc = useQueryClient()

  const { data: settings } = useQuery({ queryKey: queryKeys.settings(), queryFn: api.getSettings })

  const serverTime = settings?.journal_schedule
    ? `${String(settings.journal_schedule.hour).padStart(2,'0')}:${String(settings.journal_schedule.minute).padStart(2,'0')}`
    : '21:00'

  useEffect(() => {
    setScheduleTime(serverTime)
  }, [serverTime]) // eslint-disable-line

  // Reset edit state whenever the date changes (calendar navigation)
  useEffect(() => {
    setEditing(false)
    setEditContent('')
  }, [selectedDate])

  const saveSchedule = useMutation({
    mutationFn: () => {
      const [h, m] = scheduleTime.split(':').map(Number)
      if (!scheduleTime || isNaN(h) || isNaN(m)) return Promise.reject(new Error('Invalid time'))
      return api.updateSettings({ journal_schedule: { hour: h, minute: m } })
    },
    onSuccess: () => {
      setScheduleEditing(false)
      qc.invalidateQueries({ queryKey: queryKeys.settings() })
    },
  })

  const { data: entry, isError: entryError } = useQuery({
    queryKey: queryKeys.journal(selectedDate),
    queryFn:  () => api.getJournal(selectedDate),
    throwOnError: false,
    retry: false,
  })

  const generate = useMutation({
    mutationFn: () => api.generateJournal(selectedDate),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.journal(selectedDate) }),
  })

  const save = useMutation({
    mutationFn: (content: string) => api.updateJournal(selectedDate, content),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.journal(selectedDate) })
      setEditing(false)
    },
  })

  return {
    selectedDate,
    entry, entryError,
    editing, setEditing, editContent, setEditContent,
    generate, save,
    schedule: {
      editing: scheduleEditing, setEditing: setScheduleEditing,
      time: scheduleTime, setTime: setScheduleTime,
      serverTime, save: saveSchedule,
    },
  }
}
