import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { queryKeys } from '../api/queryKeys'
import MarkdownRenderer from './shared/MarkdownRenderer'
import { useAppDate } from '../context/DateContext'

type BtnVariant = 'ghost' | 'primary' | 'danger'
const btnStyles: Record<BtnVariant, React.CSSProperties> = {
  ghost:   { background: 'var(--bg-surface-2)', color: 'var(--text-muted)', border: '1px solid var(--border)' },
  primary: { background: 'var(--accent)',        color: '#fff',              border: 'none' },
  danger:  { background: 'var(--red-bg)',        color: 'var(--red)',         border: '1px solid rgba(248,113,113,0.2)' },
}

function Btn({
  onClick, disabled, children, variant = 'ghost',
}: {
  onClick?: () => void
  disabled?: boolean
  children: React.ReactNode
  variant?: BtnVariant
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="px-4 py-2 rounded-[9px] text-[13px] font-medium transition-all duration-150 disabled:opacity-40"
      style={btnStyles[variant]}
    >
      {children}
    </button>
  )
}

export default function Blog() {
  const { selectedDate } = useAppDate()
  const [editing, setEditing]         = useState(false)
  const [editContent, setEditContent] = useState('')
  const [scheduleTime, setScheduleTime] = useState('21:00')
  const [scheduleSaved, setScheduleSaved] = useState(false)
  const qc = useQueryClient()

  const { data: settings } = useQuery({ queryKey: queryKeys.settings(), queryFn: api.getSettings })

  useEffect(() => {
    if (settings?.blog_schedule) {
      setScheduleTime(
        `${String(settings.blog_schedule.hour).padStart(2, '0')}:${String(settings.blog_schedule.minute).padStart(2, '0')}`
      )
    }
  }, [settings?.blog_schedule?.hour, settings?.blog_schedule?.minute]) // eslint-disable-line

  // Reset edit state whenever the date changes (calendar navigation)
  useEffect(() => {
    setEditing(false)
    setEditContent('')
  }, [selectedDate])

  const saveSchedule = useMutation({
    mutationFn: () => {
      const [h, m] = scheduleTime.split(':').map(Number)
      if (!scheduleTime || isNaN(h) || isNaN(m)) return Promise.reject(new Error('Invalid time'))
      return api.updateSettings({ blog_schedule: { hour: h, minute: m } })
    },
    onSuccess: () => {
      setScheduleSaved(true)
      setTimeout(() => setScheduleSaved(false), 2000)
      qc.invalidateQueries({ queryKey: queryKeys.settings() })
    },
  })

  const { data: post } = useQuery({
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
        <div className="flex items-center gap-2">
          <span className="text-[12px]" style={{ color: 'var(--text-dim)' }}>Daily at</span>
          <input
            type="time"
            value={scheduleTime}
            onChange={e => setScheduleTime(e.target.value)}
            className="rounded-[7px] border px-2 py-1 text-[13px] outline-none"
            style={{ background: 'var(--bg-surface-2)', borderColor: 'var(--border)', color: 'var(--text)' }}
          />
          <button
            onClick={() => saveSchedule.mutate()}
            disabled={saveSchedule.isPending}
            className="px-3 py-1 rounded-[7px] text-[12px] font-medium transition-all disabled:opacity-40"
            style={scheduleSaved
              ? { background: 'var(--green-bg)', color: 'var(--green)', border: '1px solid rgba(52,211,153,0.2)' }
              : { background: 'var(--bg-surface-2)', color: 'var(--text-muted)', border: '1px solid var(--border)' }
            }
          >
            {scheduleSaved ? 'Saved' : 'Set'}
          </button>
        </div>
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
      {!post ? (
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
