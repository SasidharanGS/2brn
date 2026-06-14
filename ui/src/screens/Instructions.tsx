import { useState, type CSSProperties } from 'react'
import type { UserInstruction } from '../api/types'
import { useInstructions } from '../hooks/useInstructions'
import { Page, PageHeader, Button, QuietButton, Card, Switch, Icon } from '../ui-kit'

// Unified Instructions — one component for both skins. Logic + form/edit state
// live in useInstructions; the card's local delete-confirm toggle stays local.
export default function Instructions() {
  const {
    instructions, isLoading, enabledCount,
    createMut, updateMut, deleteMut,
    showNew, setShowNew,
    newTitle, setNewTitle, newBody, setNewBody,
    editingId, setEditingId, editTitle, setEditTitle, editBody, setEditBody,
    handleCreate, startEdit, handleSaveEdit,
  } = useInstructions()

  const subtitle = instructions.length === 0
    ? 'No instructions yet'
    : `${enabledCount} of ${instructions.length} active`

  return (
    <Page max={760}>
      <PageHeader
        title="Instructions"
        subtitle={subtitle}
        right={
          <Button variant="soft" onClick={() => { setShowNew(true); setEditingId(null) }}>
            <Icon name="plus" size={13} />New instruction
          </Button>
        }
      />

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--k-space-sm)' }}>
        {isLoading && (
          <div style={{ fontSize: 'var(--k-text-body)', color: 'var(--k-muted)' }}>Loading…</div>
        )}

        {showNew && (
          <InstructionForm
            title={newTitle} body={newBody}
            onTitleChange={setNewTitle} onBodyChange={setNewBody}
            onSave={handleCreate}
            onCancel={() => { setShowNew(false); setNewTitle(''); setNewBody('') }}
            saving={createMut.isPending}
            placeholders={{
              title: "Title (e.g. Opencode tab rename)",
              body: "Instruction (e.g. when Microsoft Edge tab title contains 'Opencode', classify the app_name as 'Opencode')",
            }}
          />
        )}

        {instructions.map(inst =>
          editingId === inst.id ? (
            <InstructionForm
              key={inst.id}
              title={editTitle} body={editBody}
              onTitleChange={setEditTitle} onBodyChange={setEditBody}
              onSave={() => handleSaveEdit(inst.id)}
              onCancel={() => setEditingId(null)}
              saving={updateMut.isPending}
            />
          ) : (
            <InstructionCard
              key={inst.id}
              inst={inst}
              onToggle={() => updateMut.mutate({ id: inst.id, patch: { enabled: !inst.enabled } })}
              onEdit={() => startEdit(inst)}
              onDelete={() => deleteMut.mutate(inst.id)}
            />
          ),
        )}

        {!isLoading && instructions.length === 0 && !showNew && (
          <EmptyInstructions />
        )}
      </div>
    </Page>
  )
}

function EmptyInstructions() {
  return (
    <div style={{
      border: '1px dashed var(--k-rule)', borderRadius: 'var(--k-radius)',
      padding: 'var(--k-empty-pad)', display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', gap: 'var(--k-space-md)', textAlign: 'center',
    }}>
      <span style={{ color: 'var(--k-muted)', opacity: 0.6 }}><Icon name="instructions" size={30} strokeWidth={1.2} /></span>
      <div style={{
        fontSize: 'var(--k-text-body)', color: 'var(--k-fg)',
        textTransform: 'var(--k-text-transform)' as CSSProperties['textTransform'],
      }}>
        No instructions yet. Add one to customise how 2brn works.
      </div>
      <div style={{
        fontFamily: 'var(--k-font-mono)', fontSize: 'var(--k-text-label)', color: 'var(--k-muted)',
        lineHeight: 1.7, maxWidth: 420,
        textTransform: 'var(--k-text-transform)' as CSSProperties['textTransform'],
      }}>
        Examples: "when Microsoft Edge tab is 'Opencode', classify app as Opencode" or
        "write Friday journal entries in Yoda voice"
      </div>
    </div>
  )
}

function InstructionCard({ inst, onToggle, onEdit, onDelete }: {
  inst: UserInstruction; onToggle: () => void; onEdit: () => void; onDelete: () => void
}) {
  const [confirming, setConfirming] = useState(false)
  return (
    <Card dim={!inst.enabled}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--k-space-sm)' }}>
        <Switch on={inst.enabled} onToggle={onToggle} label={inst.title} />
        <span style={{
          flex: 1, minWidth: 0, fontSize: 'var(--k-text-title)', color: 'var(--k-fg)',
          fontWeight: 'var(--k-emphasis-weight)' as CSSProperties['fontWeight'],
        }}>
          {inst.title}
        </span>
        <QuietButton onClick={onEdit}>edit</QuietButton>
        {confirming ? (
          <>
            <QuietButton danger onClick={onDelete}>confirm</QuietButton>
            <QuietButton onClick={() => setConfirming(false)}>cancel</QuietButton>
          </>
        ) : (
          <QuietButton danger onClick={() => setConfirming(true)}>delete</QuietButton>
        )}
      </div>
      <p style={{
        margin: 0, paddingLeft: 46, fontSize: 'var(--k-text-body)', color: 'var(--k-muted)',
        lineHeight: 1.6, whiteSpace: 'pre-wrap',
        fontWeight: 'var(--k-body-weight)' as CSSProperties['fontWeight'],
      }}>
        {inst.body}
      </p>
    </Card>
  )
}

function InstructionForm({ title, body, onTitleChange, onBodyChange, onSave, onCancel, saving, placeholders }: {
  title: string; body: string
  onTitleChange: (v: string) => void; onBodyChange: (v: string) => void
  onSave: () => void; onCancel: () => void; saving: boolean
  placeholders?: { title?: string; body?: string }
}) {
  return (
    <Card style={{ borderColor: 'var(--k-accent)' }}>
      <input
        autoFocus className="k-input" placeholder={placeholders?.title}
        value={title} onChange={e => onTitleChange(e.target.value)}
        style={{ width: '100%', fontSize: 'var(--k-text-body)' }}
      />
      <textarea
        className="k-input" placeholder={placeholders?.body} rows={3}
        value={body} onChange={e => onBodyChange(e.target.value)}
        style={{ width: '100%', resize: 'vertical', lineHeight: 1.6, fontSize: 'var(--k-text-body)' }}
      />
      <div style={{ display: 'flex', gap: 'var(--k-space-sm)', justifyContent: 'flex-end' }}>
        <Button onClick={onCancel}>Cancel</Button>
        <Button variant="soft" onClick={onSave} disabled={saving || !title.trim() || !body.trim()}>
          {saving ? 'Saving…' : 'Save'}
        </Button>
      </div>
    </Card>
  )
}
