import type { CSSProperties } from 'react'
import { useBlogPost, type BlogFrequency } from '../hooks/useBlogPost'
import {
  Page, PageHeader, Badge, Button, ReadingCard, EmptyState, Markdown, TextArea, Icon,
} from '../ui-kit'

const WEEKDAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] as const

// Unified Blog — one component for both skins. Logic lives in useBlogPost.
export default function Blog() {
  const {
    selectedDate, post, postError,
    editing, setEditing, editContent, setEditContent,
    generate, save, schedule,
  } = useBlogPost()

  const right = schedule.editing ? (
    <>
      <select
        className="k-input" value={schedule.freq}
        onChange={e => schedule.setFreq(e.target.value as BlogFrequency)}
        style={{ cursor: 'pointer' }}
      >
        <option value="daily">Daily</option>
        <option value="monthly">Monthly</option>
        <option value="weekly">Weekly</option>
      </select>

      {schedule.freq === 'monthly' && (
        <select
          className="k-input" value={schedule.day}
          onChange={e => schedule.setDay(Number(e.target.value))}
          style={{ cursor: 'pointer' }}
        >
          {Array.from({ length: 28 }, (_, i) => i + 1).map(d => (
            <option key={d} value={d}>{d === 1 ? '1st' : d === 2 ? '2nd' : d === 3 ? '3rd' : `${d}th`}</option>
          ))}
        </select>
      )}

      {schedule.freq === 'weekly' && (
        <div style={{ display: 'flex', gap: 2 }}>
          {WEEKDAYS.map(day => {
            const active = schedule.days.includes(day)
            return (
              <button
                key={day} type="button"
                className={`k-toggle-btn${active ? ' active' : ''}`}
                onClick={() => schedule.setDays(prev => (active ? prev.filter(d => d !== day) : [...prev, day]))}
                style={{ width: 30, height: 26 }}
              >
                {day[0].toUpperCase() + day[1]}
              </button>
            )
          })}
        </div>
      )}

      <input
        type="time" className="k-input"
        value={schedule.hour} onChange={e => schedule.setHour(e.target.value)}
      />
      <Button variant="primary" onClick={() => schedule.save.mutate()} disabled={schedule.save.isPending}>
        {schedule.save.isPending ? 'Saving…' : 'Update'}
      </Button>
      <Button onClick={() => { schedule.setEditing(false); schedule.reset() }}>Cancel</Button>
    </>
  ) : (
    <>
      {post?.edited_by_user && <Badge>edited</Badge>}
      <span style={{
        fontSize: 'var(--k-text-meta)', color: 'var(--k-dim)',
        textTransform: 'var(--k-text-transform)' as CSSProperties['textTransform'],
      }}>
        {schedule.summary.label}{schedule.summary.label !== 'Daily at' ? ' — ' : ' '}
        <span style={{ color: 'var(--k-fg)', fontWeight: 'var(--k-emphasis-weight)' as CSSProperties['fontWeight'] }}>
          {schedule.summary.detail}
        </span>
      </span>
      <Button onClick={() => schedule.setEditing(true)}><Icon name="edit" size={13} />Edit</Button>
    </>
  )

  return (
    <Page max={760}>
      <PageHeader title="Blog" right={right} />

      {(generate.isError || save.isError) && (
        <div style={{ fontSize: 'var(--k-text-sm)', color: 'var(--k-danger)', marginBottom: 'var(--k-space-md)' }}>
          {generate.isError ? 'Failed to generate the blog post.' : 'Failed to save changes.'}
        </div>
      )}

      {postError ? (
        <EmptyState icon="warn" title="Couldn't load the blog post">
          No blog post for {selectedDate} — the daemon may be unavailable.
        </EmptyState>

      ) : !post ? (
        <EmptyState dashed icon="blog" title={`No blog post for ${selectedDate}`}>
          <Button variant="primary" onClick={() => generate.mutate()} disabled={generate.isPending}>
            <Icon name="refresh" size={13} />{generate.isPending ? 'Generating…' : 'Generate post'}
          </Button>
        </EmptyState>

      ) : editing ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--k-space-sm)' }}>
          <TextArea value={editContent} onChange={setEditContent} />
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--k-space-sm)' }}>
            <Button onClick={() => setEditing(false)}>Cancel</Button>
            <Button variant="primary" onClick={() => save.mutate(editContent)} disabled={save.isPending}>
              {save.isPending ? 'Saving…' : 'Save'}
            </Button>
          </div>
        </div>

      ) : (
        <ReadingCard footer={
          <>
            <Button onClick={() => { setEditing(true); setEditContent(post.content ?? '') }}>
              <Icon name="edit" size={13} />Edit
            </Button>
            {!post.edited_by_user && (
              <Button onClick={() => generate.mutate()} disabled={generate.isPending}>
                <Icon name="refresh" size={13} />{generate.isPending ? 'Regenerating…' : 'Regenerate'}
              </Button>
            )}
          </>
        }>
          <Markdown content={post.content ?? ''} variant="blog" />
        </ReadingCard>
      )}
    </Page>
  )
}
