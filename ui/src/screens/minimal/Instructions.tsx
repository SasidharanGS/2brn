import { useState } from 'react'
import type { UserInstruction } from '../../api/types'
import { useInstructions } from '../../hooks/useInstructions'
import PageHeader from './PageHeader'
import Icon from './Icon'
import { GhostButton, EmptyState, Switch, lineInput } from './primitives'

const quietBtn: React.CSSProperties = {
  background: 'none', border: 'none', padding: '2px 4px', cursor: 'pointer',
  fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-wide)',
  fontWeight: 300, fontFamily: 'var(--font-sans)',
}

function InstructionForm({ title, body, onTitleChange, onBodyChange, onSave, onCancel, saving, placeholders }: {
  title: string; body: string
  onTitleChange: (v: string) => void; onBodyChange: (v: string) => void
  onSave: () => void; onCancel: () => void; saving: boolean
  placeholders?: { title?: string; body?: string }
}) {
  return (
    <div style={{
      border: '1px solid var(--muted)', padding: 'var(--space-md)',
      display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)',
    }}>
      <input
        autoFocus
        placeholder={placeholders?.title}
        value={title}
        onChange={e => onTitleChange(e.target.value)}
        style={lineInput}
      />
      <textarea
        placeholder={placeholders?.body}
        value={body}
        onChange={e => onBodyChange(e.target.value)}
        rows={3}
        style={{
          background: 'none', border: 'none', borderBottom: '1px solid var(--rule)',
          padding: '6px 0', color: 'var(--fg)', fontSize: 'var(--text-base)',
          fontWeight: 300, lineHeight: 'var(--leading-normal)', fontFamily: 'var(--font-sans)',
          outline: 'none', width: '100%', resize: 'vertical',
        }}
      />
      <div style={{ display: 'flex', gap: 'var(--space-sm)', justifyContent: 'flex-end' }}>
        <GhostButton onClick={onCancel}>cancel</GhostButton>
        <GhostButton accent onClick={onSave} disabled={saving || !title.trim() || !body.trim()}>
          {saving ? 'saving…' : 'save'}
        </GhostButton>
      </div>
    </div>
  )
}

function InstructionCard({ inst, onToggle, onEdit, onDelete }: {
  inst: UserInstruction
  onToggle: () => void
  onEdit: () => void
  onDelete: () => void
}) {
  const [confirming, setConfirming] = useState(false)
  return (
    <div style={{
      border: '1px solid var(--rule)', padding: 'var(--space-md)',
      display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)',
      opacity: inst.enabled ? 1 : 0.55,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
        <Switch on={inst.enabled} onToggle={onToggle} />
        <span style={{ flex: 1, fontSize: 'var(--text-md)', color: 'var(--fg)', fontWeight: 400, minWidth: 0 }}>
          {inst.title}
        </span>
        <button type="button" onClick={onEdit} className="m-quiet" style={quietBtn}>edit</button>
        {confirming ? (
          <>
            <button
              type="button" onClick={onDelete}
              style={{ ...quietBtn, color: 'var(--accent)' }}
            >
              confirm
            </button>
            <button type="button" onClick={() => setConfirming(false)} className="m-quiet" style={quietBtn}>
              cancel
            </button>
          </>
        ) : (
          <button type="button" onClick={() => setConfirming(true)} className="m-quiet" style={quietBtn}>
            delete
          </button>
        )}
      </div>
      <p style={{
        margin: 0, paddingLeft: 46, fontSize: 'var(--text-base)', color: 'var(--muted)',
        fontWeight: 300, lineHeight: 'var(--leading-normal)', whiteSpace: 'pre-wrap',
      }}>
        {inst.body}
      </p>
    </div>
  )
}

export default function Instructions() {
  const {
    instructions, isLoading, enabledCount,
    createMut, updateMut, deleteMut,
    showNew, setShowNew,
    newTitle, setNewTitle, newBody, setNewBody,
    editingId, setEditingId, editTitle, setEditTitle, editBody, setEditBody,
    handleCreate, startEdit, handleSaveEdit,
  } = useInstructions()

  return (
    <div style={{ padding: 'var(--space-lg)' }}>
      <PageHeader
        title="instructions"
        subtitle={instructions.length === 0 ? 'no instructions yet' : `${enabledCount} of ${instructions.length} active`}
        right={
          <GhostButton accent onClick={() => { setShowNew(true); setEditingId(null) }}>
            <Icon name="plus" size={13} />new instruction
          </GhostButton>
        }
      />

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)', maxWidth: 760 }}>
        {isLoading && (
          <div style={{ fontSize: 'var(--text-base)', color: 'var(--muted)', fontWeight: 300 }}>loading…</div>
        )}

        {showNew && (
          <InstructionForm
            title={newTitle}
            body={newBody}
            onTitleChange={setNewTitle}
            onBodyChange={setNewBody}
            onSave={handleCreate}
            onCancel={() => { setShowNew(false); setNewTitle(''); setNewBody('') }}
            saving={createMut.isPending}
            placeholders={{
              title: "title (e.g. opencode tab rename)",
              body: "instruction (e.g. when microsoft edge tab title contains 'opencode', classify the app_name as 'opencode')",
            }}
          />
        )}

        {instructions.map(inst =>
          editingId === inst.id ? (
            <InstructionForm
              key={inst.id}
              title={editTitle}
              body={editBody}
              onTitleChange={setEditTitle}
              onBodyChange={setEditBody}
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
          )
        )}

        {!isLoading && instructions.length === 0 && !showNew && (
          <EmptyState dashed icon={<Icon name="instructions" size={30} strokeWidth={1.2} />}>
            <div style={{ color: 'var(--fg)', marginBottom: 'var(--space-md)' }}>
              no instructions yet. add one to customise how 2brn works.
            </div>
            <div style={{
              fontFamily: 'var(--font-mono)', fontSize: '0.7rem', color: 'var(--muted)',
              lineHeight: 'var(--leading-loose)',
            }}>
              examples: "when microsoft edge tab is 'opencode', classify app as opencode" or
              "write friday journal entries in yoda voice"
            </div>
          </EmptyState>
        )}
      </div>
    </div>
  )
}
