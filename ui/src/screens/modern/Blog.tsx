import MarkdownRenderer from '../../components/shared/MarkdownRenderer'
import Btn from '../../components/shared/Btn'
import { useBlogPost, type BlogFrequency } from '../../hooks/useBlogPost'

export default function Blog() {
  const {
    selectedDate, post, postError,
    editing, setEditing, editContent, setEditContent,
    generate, save, schedule,
  } = useBlogPost()

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
        {schedule.editing ? (
          <div className="flex items-center gap-2 flex-wrap justify-end">
            <select
              value={schedule.freq}
              onChange={e => schedule.setFreq(e.target.value as BlogFrequency)}
              className="rounded-[7px] border px-2 py-1 text-[13px] outline-none"
              style={{ background: 'var(--bg-surface-2)', borderColor: 'var(--border)', color: 'var(--text)' }}
            >
              <option value="daily">Daily</option>
              <option value="monthly">Monthly</option>
              <option value="weekly">Weekly</option>
            </select>

            {schedule.freq === 'monthly' && (
              <select
                value={schedule.day}
                onChange={e => schedule.setDay(Number(e.target.value))}
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

            {schedule.freq === 'weekly' && (
              <div className="flex gap-1">
                {(['mon','tue','wed','thu','fri','sat','sun'] as const).map(day => {
                  const active = schedule.days.includes(day)
                  return (
                    <button
                      key={day}
                      onClick={() => schedule.setDays(prev =>
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
              value={schedule.hour}
              onChange={e => schedule.setHour(e.target.value)}
              className="rounded-[7px] border px-2 py-1 text-[13px] outline-none"
              style={{ background: 'var(--bg-surface-2)', borderColor: 'var(--border)', color: 'var(--text)' }}
            />

            <button
              onClick={() => schedule.save.mutate()}
              disabled={schedule.save.isPending}
              className="px-3 py-1 rounded-[9px] text-[12px] font-medium transition-all disabled:opacity-40"
              style={{ background: 'var(--accent)', color: '#fff', border: 'none' }}
            >
              {schedule.save.isPending ? 'Saving…' : 'Update'}
            </button>
            <button
              onClick={() => { schedule.setEditing(false); schedule.reset() }}
              className="px-3 py-1 rounded-[9px] text-[12px] font-medium transition-all"
              style={{ background: 'var(--bg-surface-2)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}
            >
              Cancel
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <span className="text-[12px]" style={{ color: 'var(--text-dim)' }}>
              {schedule.summary.label}{schedule.summary.label !== 'Daily at' ? ' — ' : ' '}
              <span className="font-medium" style={{ color: 'var(--text)' }}>
                {schedule.summary.detail}
              </span>
            </span>
            <button
              onClick={() => schedule.setEditing(true)}
              className="px-3 py-1 rounded-[9px] text-[12px] font-medium transition-all"
              style={{ background: 'var(--bg-surface-2)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}
            >
              Edit
            </button>
          </div>
        )}
      </div>

      {/* Error banners */}
      {generate.isError && (
        <div className="mb-4 px-4 py-3 rounded-[9px] text-[13px] border"
          style={{ background: 'var(--red-bg)', color: 'var(--red)', borderColor: 'rgba(248,113,113,0.2)' }}>
          Failed to generate blog post.
        </div>
      )}
      {save.isError && (
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
          <Btn variant="primary" onClick={() => generate.mutate()} disabled={generate.isPending}>
            {generate.isPending ? 'Generating…' : 'Generate Post'}
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
            <Btn variant="primary" onClick={() => save.mutate(editContent)} disabled={save.isPending}>
              {save.isPending ? 'Saving…' : 'Save'}
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
              <Btn onClick={() => generate.mutate()} disabled={generate.isPending}>
                {generate.isPending ? 'Regenerating…' : 'Regenerate'}
              </Btn>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
