import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { queryKeys } from '../api/queryKeys'
import { useAppDate } from '../context/DateContext'

export type BlogFrequency = 'daily' | 'monthly' | 'weekly'

/** Blog post data, edit state, and schedule control for the selected date. */
export function useBlogPost() {
  const { selectedDate } = useAppDate()
  const [editing, setEditing]                 = useState(false)
  const [editContent, setEditContent]         = useState('')
  const [scheduleEditing, setScheduleEditing] = useState(false)
  const [scheduleFreq, setScheduleFreq]       = useState<BlogFrequency>('daily')
  const [scheduleHour, setScheduleHour]       = useState('21:00')
  const [scheduleDay, setScheduleDay]         = useState(1)
  const [scheduleDays, setScheduleDays]       = useState<string[]>([])
  const qc = useQueryClient()

  const { data: settings } = useQuery({ queryKey: queryKeys.settings(), queryFn: api.getSettings })

  const srv = settings?.blog_schedule

  // Sync form state from server whenever the server value changes
  useEffect(() => {
    if (srv) {
      setScheduleFreq(srv.frequency)
      setScheduleHour(`${String(srv.hour).padStart(2,'0')}:${String(srv.minute).padStart(2,'0')}`)
      setScheduleDay(srv.day)
      setScheduleDays(srv.days_of_week)
    }
  }, [srv?.frequency, srv?.hour, srv?.minute, srv?.day, srv?.days_of_week?.join(',')]) // eslint-disable-line

  // Reset edit state whenever the date changes
  useEffect(() => {
    setEditing(false)
    setEditContent('')
  }, [selectedDate])

  const saveSchedule = useMutation({
    mutationFn: () => {
      const [h, m] = scheduleHour.split(':').map(Number)
      if (!scheduleHour || isNaN(h) || isNaN(m)) return Promise.reject(new Error('Invalid time'))
      return api.updateSettings({
        blog_schedule: { frequency: scheduleFreq, hour: h, minute: m, day: scheduleDay, days_of_week: scheduleDays },
      })
    },
    onSuccess: () => {
      setScheduleEditing(false)
      qc.invalidateQueries({ queryKey: queryKeys.settings() })
    },
  })

  /** Reset the schedule form back to the server values (cancel editing). */
  const resetScheduleForm = () => {
    if (srv) {
      setScheduleFreq(srv.frequency)
      setScheduleHour(`${String(srv.hour).padStart(2,'0')}:${String(srv.minute).padStart(2,'0')}`)
      setScheduleDay(srv.day)
      setScheduleDays(srv.days_of_week)
    }
  }

  // Human-readable summary built from local state (always populated — defaults to 21:00 daily)
  const scheduleSummary = (() => {
    const time = scheduleHour
    if (scheduleFreq === 'monthly') {
      const suffix = scheduleDay === 1 ? 'st' : scheduleDay === 2 ? 'nd' : scheduleDay === 3 ? 'rd' : 'th'
      return { label: 'Monthly', detail: `${scheduleDay}${suffix} at ${time}` }
    }
    if (scheduleFreq === 'weekly') {
      const detail = scheduleDays.length
        ? `${scheduleDays.map(d => d[0].toUpperCase() + d[1]).join(', ')} at ${time}`
        : `no days set`
      return { label: 'Weekly', detail }
    }
    return { label: 'Daily at', detail: time }
  })()

  const { data: post, isError: postError } = useQuery({
    queryKey: queryKeys.blog(selectedDate),
    queryFn:  () => api.getBlogPost(selectedDate),
    throwOnError: false,
    retry: false,
  })

  const generate = useMutation({
    mutationFn: () => api.generateBlogPost(selectedDate),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.blog(selectedDate) }),
  })

  const save = useMutation({
    mutationFn: (content: string) => api.updateBlogPost(selectedDate, content),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.blog(selectedDate) })
      setEditing(false)
    },
  })

  return {
    selectedDate,
    post, postError,
    editing, setEditing, editContent, setEditContent,
    generate, save,
    schedule: {
      editing: scheduleEditing, setEditing: setScheduleEditing,
      freq: scheduleFreq, setFreq: setScheduleFreq,
      hour: scheduleHour, setHour: setScheduleHour,
      day: scheduleDay, setDay: setScheduleDay,
      days: scheduleDays, setDays: setScheduleDays,
      summary: scheduleSummary, save: saveSchedule, reset: resetScheduleForm,
    },
  }
}
