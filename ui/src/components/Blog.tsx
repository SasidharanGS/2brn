import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { queryKeys } from '../api/queryKeys'
import MarkdownRenderer from './shared/MarkdownRenderer'
import { useAppDate } from '../context/DateContext'
import Btn from './shared/Btn'

export default function Blog() {
  const { selectedDate } = useAppDate()
  const [editing, setEditing]               = useState(false)
  const [editContent, setEditContent]       = useState('')
  const [scheduleEditing, setScheduleEditing] = useState(false)
  const [scheduleFreq, setScheduleFreq]     = useState<'daily' | 'monthly' | 'weekly'>('daily')
  const [scheduleHour, setScheduleHour]     = useState('21:00')
  const [scheduleDay, setScheduleDay]       = useState(1)
  const [scheduleDays, setScheduleDays]     = useState<string[]>([])
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
  }, [srv?.frequency, srv?.hour, srv?.minute, srv?.day, srv?.days_of_week?.join(',')])

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

  const generateMutation = useMutation({
    mutationFn: () => api.generateBlogPost(selectedDate),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.blog(selectedDate) }),
  })

  const saveMutation = useMutation({
    mutationFn: (content: string) => api.updateBlogPost(selectedDate, content),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.blog(selectedDate) })
      setEditing(false)
    },
  })

  return (
    <div className="page-enter p-7 max-w-[760px] mx-auto">

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <h1 className="text-[19px] font-semibold tracking-tight" style={{ color: 'var(--text)' }}>
            Blog
          </h1>
          {post?.edited_by_user && (
            <span
              className="text-[11px] px-2 py-0.5 rounded-full font-medium"
              style={{ background: 'var(--amber-bg)', color: 'var(--amber)' }}
            >
              edited
            </span>
          )}
        </div>

        {/* Schedule control */}
        {scheduleEditing ? (
          <div className="flex items-center gap-2 flex-wrap justify-end">
            <select
              value={scheduleFreq}
              onChange={e => setScheduleFreq(e.target.value as 'daily' | 'monthly' | 'weekly')}
              className="rounded-[7px] border px-2 py-1 text-[13px] outline-none"
              style={{ background: 'var(--bg-surface-2)', borderColor: 'var(--border)', color: 'var(--text)' }}
            >
              <option value="daily">Daily</option>
              <option value="monthly">Monthly</option>
              <option value="weekly">Weekly</option>
            </select>

            {scheduleFreq === 'monthly' && (
              <select
                value={scheduleDay}
                onChange={e => setScheduleDay(Number(e.target.value))}
                className="rounded-[7px] border px-2 py-1 text-[13px] outline-none"
                style={{ background: 'var(--bg-surface-2)', borderColor: 'var(--border)', color: 'var(--text)' }}
              >
                {Array.from({ length: 28 }, (_, i) => i + 1).map(d => (
                  <option key={d} value={d}>
                    {d === 1 ? '1st' : d === 2 ? '2nd' : d === 3 ? '3rd' : `${d}th`}
                  </option>
                ))}
              </select>
            )}

            {scheduleFreq === 'weekly' && (
              <div className="flex gap-1">
                {(['mon','tue','wed','thu','fri','sat','sun'] as const).map(day => {
                  const active = scheduleDays.includes(day)
                  return (
                    <button
                      key={day}
                      onClick={() => setScheduleDays(prev =>
                        active ? prev.filter(d => d !== day) : [...prev, day]
                      )}
                      className="w-8 h-7 rounded-[6px] text-[11px] font-medium transition-all"
                      style={active
                        ? { background: 'var(--accent)', color: '#fff', border: 'none' }
                        : { background: 'var(--bg-surface-2)', color: 'var(--text-muted)', border: '1px solid var(--border)' }
                      }
                    >
                      {day[0].toUpperCase()}{day[1]}
                    </button>
                  )
                })}
              </div>
            )}

            <input
              type="time"
              value={scheduleHour}
              onChange={e => setScheduleHour(e.target.value)}
              className="rounded-[7px] border px-2 py-1 text-[13px] outline-none"
              style={{ background: 'var(--bg-surface-2)', borderColor: 'var(--border)', color: 'var(--text)' }}
            />

            <button
              onClick={() => saveSchedule.mutate()}
              disabled={saveSchedule.isPending}
              className="px-3 py-1 rounded-[9px] text-[12px] font-medium transition-all disabled:opacity-40"
              style={{ background: 'var(--accent)', color: '#fff', border: 'none' }}
            >
              {saveSchedule.isPending ? 'Saving…' : 'Update'}
            </button>
            <button
              onClick={() => {
                setScheduleEditing(false)
                if (srv) {
                  setScheduleFreq(srv.frequency)
                  setScheduleHour(`${String(srv.hour).padStart(2,'0')}:${String(srv.minute).padStart(2,'0')}`)
                  setScheduleDay(srv.day)
                  setScheduleDays(srv.days_of_week)
                }
              }}
              className="px-3 py-1 rounded-[9px] text-[12px] font-medium transition-all"
              style={{ background: 'var(--bg-surface-2)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}
            >
              Cancel
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <span className="text-[12px]" style={{ color: 'var(--text-dim)' }}>
              {scheduleSummary.label}{scheduleSummary.label !== 'Daily at' ? ' — ' : ' '}
              <span className="font-medium" style={{ color: 'var(--text)' }}>
                {scheduleSummary.detail}
              </span>
            </span>
            <button
              onClick={() => setScheduleEditing(true)}
              className="px-3 py-1 rounded-[9px] text-[12px] font-medium transition-all"
              style={{ background: 'var(--bg-surface-2)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}
            >
              Edit
            </button>
          </div>
        )}
      </div>

      {/* Error banners */}
      {generateMutation.isError && (
        <div className="mb-4 px-4 py-3 rounded-[9px] text-[13px] border"
          style={{ background: 'var(--red-bg)', color: 'var(--red)', borderColor: 'rgba(248,113,113,0.2)' }}>
          Failed to generate blog post.
        </div>
      )}
      {saveMutation.isError && (
        <div className="mb-4 px-4 py-3 rounded-[9px] text-[13px] border"
          style={{ background: 'var(--red-bg)', color: 'var(--red)', borderColor: 'rgba(248,113,113,0.2)' }}>
          Failed to save changes.
        </div>
      )}

      {/* States */}
      {postError ? (
        <div
          className="rounded-[12px] border p-10 text-center"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
        >
          <div className="text-4xl mb-4 opacity-20">⚠️</div>
          <p className="text-[14px]" style={{ color: 'var(--text-muted)' }}>
            Couldn't load the blog post for {selectedDate}. The daemon may be unavailable.
          </p>
        </div>
      ) : !post ? (
        <div
          className="rounded-[12px] border p-10 text-center"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
        >
          <div className="text-4xl mb-4 opacity-20">✍️</div>
          <p className="text-[14px] mb-5" style={{ color: 'var(--text-muted)' }}>
            No blog post for {selectedDate}
          </p>
          <Btn variant="primary" onClick={() => generateMutation.mutate()} disabled={generateMutation.isPending}>
            {generateMutation.isPending ? 'Generating…' : 'Generate Post'}
          </Btn>
        </div>

      ) : editing ? (
        <div className="space-y-3">
          <textarea
            value={editContent}
            onChange={e => setEditContent(e.target.value)}
            rows={22}
            className="w-full rounded-[12px] border px-4 py-3 text-[14px] font-mono resize-none outline-none"
            style={{
              background: 'var(--bg-surface)',
              borderColor: 'var(--border-2)',
              color: 'var(--text)',
              lineHeight: 1.7,
            }}
          />
          <div className="flex justify-end gap-2">
            <Btn onClick={() => setEditing(false)}>Cancel</Btn>
            <Btn variant="primary" onClick={() => saveMutation.mutate(editContent)} disabled={saveMutation.isPending}>
              {saveMutation.isPending ? 'Saving…' : 'Save'}
            </Btn>
          </div>
        </div>

      ) : (
        <div
          className="rounded-[12px] border p-6"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
        >
          <MarkdownRenderer content={post.content ?? ''} />
          <div className="flex gap-2 mt-6 pt-4 border-t" style={{ borderColor: 'var(--border)' }}>
            <Btn onClick={() => { setEditing(true); setEditContent(post.content ?? '') }}>Edit</Btn>
            {!post.edited_by_user && (
              <Btn onClick={() => generateMutation.mutate()} disabled={generateMutation.isPending}>
                {generateMutation.isPending ? 'Regenerating…' : 'Regenerate'}
              </Btn>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
