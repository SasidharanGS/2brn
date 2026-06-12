import { useJournalEntry } from '../../hooks/useJournalEntry'
import PageHeader from './PageHeader'
import DocCard from './DocCard'
import Prose from './Prose'
import Icon from './Icon'
import { GhostButton, Pill, EmptyState, lineInput } from './primitives'

export default function Journal() {
  const {
    selectedDate, entry, entryError,
    editing, setEditing, editContent, setEditContent,
    generate, save, schedule,
  } = useJournalEntry()

  return (
    <div style={{ padding: 'var(--space-lg)' }}>
      <PageHeader
        title="journal"
        right={
          schedule.editing ? (
            <>
              <input
                type="time"
                value={schedule.time}
                onChange={e => schedule.setTime(e.target.value)}
                style={{ ...lineInput, width: 'auto' }}
              />
              <GhostButton onClick={() => schedule.save.mutate()} disabled={schedule.save.isPending}>
                {schedule.save.isPending ? 'saving…' : 'update'}
              </GhostButton>
              <GhostButton onClick={() => { schedule.setEditing(false); schedule.setTime(schedule.serverTime) }}>
                cancel
              </GhostButton>
            </>
          ) : (
            <>
              {entry?.edited_by_user && <Pill>edited</Pill>}
              <span style={{
                fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-wide)',
                color: 'var(--muted)', fontWeight: 300,
              }}>
                daily at <span style={{ color: 'var(--fg)', fontWeight: 400 }}>{schedule.serverTime}</span>
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
          {generate.isError ? 'failed to generate the journal entry.' : 'failed to save changes.'}
        </div>
      )}

      {entryError ? (
        <EmptyState icon={<Icon name="warn" size={28} strokeWidth={1.2} />} title="couldn't load the journal">
          no response for {selectedDate} — the daemon may be unavailable.
        </EmptyState>

      ) : !entry ? (
        <EmptyState
          dashed
          icon={<Icon name="journal" size={28} strokeWidth={1.2} />}
          title={`no journal entry for ${selectedDate}`}
        >
          <GhostButton accent onClick={() => generate.mutate()} disabled={generate.isPending}>
            <Icon name="refresh" size={13} />
            {generate.isPending ? 'generating…' : 'generate entry'}
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
              <GhostButton onClick={() => { setEditing(true); setEditContent(entry.content ?? '') }}>
                <Icon name="edit" size={13} />edit
              </GhostButton>
              {!entry.edited_by_user && (
                <GhostButton onClick={() => generate.mutate()} disabled={generate.isPending}>
                  <Icon name="refresh" size={13} />
                  {generate.isPending ? 'regenerating…' : 'regenerate'}
                </GhostButton>
              )}
            </>
          }
        >
          <Prose content={entry.content ?? ''} variant="journal" />
        </DocCard>
      )}
    </div>
  )
}
