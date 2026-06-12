import { useState } from 'react'
import type { UserInstruction } from '../../api/types'
import Toggle from '../../components/shared/Toggle'
import { useInstructions } from '../../hooks/useInstructions'

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
    <div className="flex flex-col h-full overflow-hidden">
      <div
        className="flex items-center justify-between px-6 py-4 shrink-0 border-b"
        style={{ borderColor: 'var(--border)' }}
      >
        <div>
          <h1 className="text-[16px] font-semibold" style={{ color: 'var(--text)' }}>
            Instructions
          </h1>
          <p className="text-[12px] mt-0.5" style={{ color: 'var(--text-dim)' }}>
            {instructions.length === 0
              ? 'No instructions yet'
              : `${enabledCount} of ${instructions.length} active`}
          </p>
        </div>
        <button
          onClick={() => { setShowNew(true); setEditingId(null) }}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-[8px] text-[12px] font-medium transition-all"
          style={{ background: 'var(--accent-glow)', color: 'var(--accent)', border: '1px solid var(--border-focus)' }}
        >
          + new instruction
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4 flex flex-col gap-3">
        {isLoading && (
          <p className="text-[12px]" style={{ color: 'var(--text-dim)' }}>Loading…</p>
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
            placeholders={{ title: 'Title (e.g. Opencode tab rename)', body: "Instruction (e.g. When Microsoft Edge tab title contains 'Opencode', classify the app_name as 'Opencode')" }}
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
          <div
            className="flex flex-col items-center justify-center py-20 gap-3 rounded-[12px]"
            style={{ border: '1px dashed var(--border-2)' }}
          >
            <span className="text-[28px]">📋</span>
            <p className="text-[13px]" style={{ color: 'var(--text-muted)' }}>
              No instructions yet. Add one to customise how 2brn works.
            </p>
            <p className="text-[11px] font-mono max-w-sm text-center" style={{ color: 'var(--text-dim)' }}>
              Examples: "When Microsoft Edge tab is 'Opencode', classify app as Opencode" or
              "Write Friday journal entries in Yoda voice"
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

function InstructionCard({
  inst, onToggle, onEdit, onDelete,
}: {
  inst: UserInstruction
  onToggle: () => void
  onEdit: () => void
  onDelete: () => void
}) {
  const [confirming, setConfirming] = useState(false)
  return (
    <div
      className="rounded-[10px] p-4 flex flex-col gap-2 transition-all"
      style={{
        background: 'var(--bg-surface)',
        border: `1px solid ${inst.enabled ? 'var(--border-2)' : 'var(--border)'}`,
        opacity: inst.enabled ? 1 : 0.55,
      }}
    >
      <div className="flex items-center gap-3">
        <Toggle enabled={inst.enabled} onToggle={onToggle} />
        <span
          className="flex-1 text-[13px] font-medium"
          style={{ color: 'var(--text)' }}
        >
          {inst.title}
        </span>
        <button
          onClick={onEdit}
          className="text-[11px] font-mono px-2 py-0.5 rounded-[5px] transition-all"
          style={{ color: 'var(--text-dim)', background: 'var(--bg-surface-2)' }}
        >
          edit
        </button>
        {confirming ? (
          <>
            <button
              onClick={onDelete}
              className="text-[11px] font-mono px-2 py-0.5 rounded-[5px] transition-all"
              style={{ color: '#fff', background: 'var(--red)' }}
            >
              confirm
            </button>
            <button
              onClick={() => setConfirming(false)}
              className="text-[11px] font-mono px-2 py-0.5 rounded-[5px] transition-all"
              style={{ color: 'var(--text-dim)', background: 'var(--bg-surface-2)' }}
            >
              cancel
            </button>
          </>
        ) : (
          <button
            onClick={() => setConfirming(true)}
            className="text-[11px] font-mono px-2 py-0.5 rounded-[5px] transition-all"
            style={{ color: 'var(--red)', background: 'var(--red-bg)' }}
          >
            delete
          </button>
        )}
      </div>
      <p
        className="text-[12px] leading-relaxed pl-[44px]"
        style={{ color: 'var(--text-muted)', whiteSpace: 'pre-wrap' }}
      >
        {inst.body}
      </p>
    </div>
  )
}

function InstructionForm({
  title, body, onTitleChange, onBodyChange, onSave, onCancel, saving,
  placeholders,
}: {
  title: string; body: string
  onTitleChange: (v: string) => void; onBodyChange: (v: string) => void
  onSave: () => void; onCancel: () => void; saving: boolean
  placeholders?: { title?: string; body?: string }
}) {
  return (
    <div
      className="rounded-[10px] p-4 flex flex-col gap-3"
      style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-focus)' }}
    >
      <input
        autoFocus
        placeholder={placeholders?.title}
        value={title}
        onChange={e => onTitleChange(e.target.value)}
        className="w-full text-[13px] px-3 py-2 rounded-[7px] outline-none"
        style={{
          background: 'var(--bg-input)',
          border: '1px solid var(--border-2)',
          color: 'var(--text)',
        }}
      />
      <textarea
        placeholder={placeholders?.body}
        value={body}
        onChange={e => onBodyChange(e.target.value)}
        rows={3}
        className="w-full text-[12px] px-3 py-2 rounded-[7px] outline-none resize-none leading-relaxed"
        style={{
          background: 'var(--bg-input)',
          border: '1px solid var(--border-2)',
          color: 'var(--text)',
        }}
      />
      <div className="flex gap-2 justify-end">
        <button
          onClick={onCancel}
          className="text-[12px] px-3 py-1.5 rounded-[7px] transition-all"
          style={{ color: 'var(--text-dim)', background: 'var(--bg-surface-2)' }}
        >
          cancel
        </button>
        <button
          onClick={onSave}
          disabled={saving || !title.trim() || !body.trim()}
          className="text-[12px] px-3 py-1.5 rounded-[7px] font-medium transition-all disabled:opacity-40"
          style={{ background: 'var(--accent-glow)', color: 'var(--accent)', border: '1px solid var(--border-focus)' }}
        >
          {saving ? 'saving…' : 'save'}
        </button>
      </div>
    </div>
  )
}
