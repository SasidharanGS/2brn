import type { CSSProperties } from 'react'
import { useJournalEntry } from '../hooks/useJournalEntry'
import {
  Page, PageHeader, Badge, Button, ReadingCard, EmptyState, Markdown, TextArea, Icon,
} from '../ui-kit'

// Unified Journal — one component for both skins. Logic lives in useJournalEntry;
// presentation is the ui-kit, cased/styled per skin via the token contract.
export default function Journal() {
  const {
    selectedDate, entry, entryError,
    editing, setEditing, editContent, setEditContent,
    generate, save, schedule,
  } = useJournalEntry()

  const right = schedule.editing ? (
    <>
      <input
        type="time" className="k-input"
        value={schedule.time} onChange={e => schedule.setTime(e.target.value)}
      />
      <Button variant="primary" onClick={() => schedule.save.mutate()} disabled={schedule.save.isPending}>
        {schedule.save.isPending ? 'Saving…' : 'Update'}
      </Button>
      <Button onClick={() => { schedule.setEditing(false); schedule.setTime(schedule.serverTime) }}>Cancel</Button>
    </>
  ) : (
    <>
      {entry?.edited_by_user && <Badge>edited</Badge>}
      <span style={{
        fontSize: 'var(--k-text-meta)', color: 'var(--k-dim)',
        textTransform: 'var(--k-text-transform)' as CSSProperties['textTransform'],
      }}>
        Daily at <span style={{ color: 'var(--k-fg)', fontWeight: 'var(--k-emphasis-weight)' as CSSProperties['fontWeight'] }}>{schedule.serverTime}</span>
      </span>
      <Button onClick={() => schedule.setEditing(true)}><Icon name="edit" size={13} />Edit</Button>
    </>
  )

  return (
    <Page max={760}>
      <PageHeader title="Journal" right={right} />

      {(generate.isError || save.isError) && (
        <div style={{ fontSize: 'var(--k-text-sm)', color: 'var(--k-danger)', marginBottom: 'var(--k-space-md)' }}>
          {generate.isError ? 'Failed to generate the journal entry.' : 'Failed to save changes.'}
        </div>
      )}

      {entryError ? (
        <EmptyState icon="warn" title="Couldn't load the journal">
          No journal for {selectedDate} — the daemon may be unavailable.
        </EmptyState>

      ) : !entry ? (
        <EmptyState dashed icon="journal" title={`No journal entry for ${selectedDate}`}>
          <Button variant="primary" onClick={() => generate.mutate()} disabled={generate.isPending}>
            <Icon name="refresh" size={13} />{generate.isPending ? 'Generating…' : 'Generate entry'}
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
            <Button onClick={() => { setEditing(true); setEditContent(entry.content ?? '') }}>
              <Icon name="edit" size={13} />Edit
            </Button>
            {!entry.edited_by_user && (
              <Button onClick={() => generate.mutate()} disabled={generate.isPending}>
                <Icon name="refresh" size={13} />{generate.isPending ? 'Regenerating…' : 'Regenerate'}
              </Button>
            )}
          </>
        }>
          <Markdown content={entry.content ?? ''} variant="journal" />
        </ReadingCard>
      )}
    </Page>
  )
}
