import { useBlogPost, type BlogFrequency } from '../../hooks/useBlogPost'
import PageHeader from './PageHeader'
import DocCard from './DocCard'
import Prose from './Prose'
import Icon from './Icon'
import { GhostButton, Pill, EmptyState, lineInput } from './primitives'

const WEEKDAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] as const

export default function Blog() {
  const {
    selectedDate, post, postError,
    editing, setEditing, editContent, setEditContent,
    generate, save, schedule,
  } = useBlogPost()

  return (
    <div style={{ padding: 'var(--space-lg)' }}>
      <PageHeader
        title="blog"
        right={
          schedule.editing ? (
            <>
              <select
                value={schedule.freq}
                onChange={e => schedule.setFreq(e.target.value as BlogFrequency)}
                style={{ ...lineInput, width: 'auto', cursor: 'pointer', appearance: 'none', borderRadius: 0 }}
              >
                <option value="daily">daily</option>
                <option value="monthly">monthly</option>
                <option value="weekly">weekly</option>
              </select>

              {schedule.freq === 'monthly' && (
                <select
                  value={schedule.day}
                  onChange={e => schedule.setDay(Number(e.target.value))}
                  style={{ ...lineInput, width: 'auto', cursor: 'pointer', appearance: 'none', borderRadius: 0 }}
                >
                  {Array.from({ length: 28 }, (_, i) => i + 1).map(d => (
                    <option key={d} value={d}>
                      {d === 1 ? '1st' : d === 2 ? '2nd' : d === 3 ? '3rd' : `${d}th`}
                    </option>
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
                        onClick={() => schedule.setDays(prev =>
                          active ? prev.filter(d => d !== day) : [...prev, day]
                        )}
                        style={{
                          width: 28, height: 24, border: '1px solid var(--rule)', cursor: 'pointer',
                          background: active ? 'var(--fg)' : 'none',
                          color: active ? 'var(--bg)' : 'var(--muted)',
                          fontSize: 'var(--text-2xs)', fontWeight: 300, fontFamily: 'var(--font-sans)',
                          transition: 'color 0.2s ease',
                        }}
                      >
                        {day.slice(0, 2)}
                      </button>
                    )
                  })}
                </div>
              )}

              <input
                type="time"
                value={schedule.hour}
                onChange={e => schedule.setHour(e.target.value)}
                style={{ ...lineInput, width: 'auto' }}
              />
              <GhostButton onClick={() => schedule.save.mutate()} disabled={schedule.save.isPending}>
                {schedule.save.isPending ? 'saving…' : 'update'}
              </GhostButton>
              <GhostButton onClick={() => { schedule.setEditing(false); schedule.reset() }}>
                cancel
              </GhostButton>
            </>
          ) : (
            <>
              {post?.edited_by_user && <Pill>edited</Pill>}
              <span style={{
                fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-wide)',
                color: 'var(--muted)', fontWeight: 300,
              }}>
                {schedule.summary.label.toLowerCase()}{schedule.summary.label !== 'Daily at' ? ' — ' : ' '}
                <span style={{ color: 'var(--fg)', fontWeight: 400 }}>
                  {schedule.summary.detail.toLowerCase()}
                </span>
              </span>
              <GhostButton onClick={() => schedule.setEditing(true)}>
                <Icon name="edit" size={13} />edit
              </GhostButton>
            </>
          )
        }
      />

      {(generate.isError || save.isError) && (
        <div style={{
          fontSize: 'var(--text-base)', color: 'var(--accent)', fontWeight: 300,
          marginBottom: 'var(--space-md)',
        }}>
          {generate.isError ? 'failed to generate the blog post.' : 'failed to save changes.'}
        </div>
      )}

      {postError ? (
        <EmptyState icon={<Icon name="warn" size={28} strokeWidth={1.2} />} title="couldn't load the blog post">
          no response for {selectedDate} — the daemon may be unavailable.
        </EmptyState>

      ) : !post ? (
        <EmptyState
          dashed
          icon={<Icon name="blog" size={28} strokeWidth={1.2} />}
          title={`no blog post for ${selectedDate}`}
        >
          <GhostButton accent onClick={() => generate.mutate()} disabled={generate.isPending}>
            <Icon name="refresh" size={13} />
            {generate.isPending ? 'generating…' : 'generate post'}
          </GhostButton>
        </EmptyState>

      ) : editing ? (
        <div style={{ maxWidth: 760, display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
          <textarea
            value={editContent}
            onChange={e => setEditContent(e.target.value)}
            rows={22}
            style={{
              background: 'none', border: '1px solid var(--rule)', padding: 'var(--space-sm)',
              color: 'var(--fg)', fontSize: 'var(--text-base)', fontWeight: 300,
              lineHeight: 'var(--leading-relaxed)', fontFamily: 'var(--font-sans)',
              outline: 'none', width: '100%', resize: 'vertical', boxSizing: 'border-box',
            }}
          />
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-sm)' }}>
            <GhostButton onClick={() => setEditing(false)}>cancel</GhostButton>
            <GhostButton onClick={() => save.mutate(editContent)} disabled={save.isPending}>
              {save.isPending ? 'saving…' : 'save'}
            </GhostButton>
          </div>
        </div>

      ) : (
        <DocCard
          footer={
            <>
              <GhostButton onClick={() => { setEditing(true); setEditContent(post.content ?? '') }}>
                <Icon name="edit" size={13} />edit
              </GhostButton>
              {!post.edited_by_user && (
                <GhostButton onClick={() => generate.mutate()} disabled={generate.isPending}>
                  <Icon name="refresh" size={13} />
                  {generate.isPending ? 'regenerating…' : 'regenerate'}
                </GhostButton>
              )}
            </>
          }
        >
          <Prose content={post.content ?? ''} variant="blog" />
        </DocCard>
      )}
    </div>
  )
}
