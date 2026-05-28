import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { UserInstruction } from '../api/types'
import Toggle from './shared/Toggle'

const QK = 'instructions'

export default function Instructions() {
  const qc = useQueryClient()
  const { data: instructions = [], isLoading } = useQuery({
    queryKey: [QK],
    queryFn: api.listInstructions,
  })

  const createMut = useMutation({
    mutationFn: ({ title, body }: { title: string; body: string }) =>
      api.createInstruction(title, body, true),
    onSuccess: () => qc.invalidateQueries({ queryKey: [QK] }),
  })
  const updateMut = useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: Partial<Pick<UserInstruction, 'title' | 'body' | 'enabled'>> }) =>
      api.updateInstruction(id, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: [QK] }),
  })
  const deleteMut = useMutation({
    mutationFn: (id: number) => api.deleteInstruction(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: [QK] }),
  })

  const [showNew, setShowNew] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newBody, setNewBody] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [editBody, setEditBody] = useState('')

  function handleCreate() {
    if (!newTitle.trim() || !newBody.trim()) return
    createMut.mutate({ title: newTitle.trim(), body: newBody.trim() }, {
      onSuccess: () => { setShowNew(false); setNewTitle(''); setNewBody('') },
    })
  }

  function startEdit(inst: UserInstruction) {
    setEditingId(inst.id)
    setEditTitle(inst.title)
    setEditBody(inst.body)
  }

  function handleSaveEdit(id: number) {
    if (!editTitle.trim() || !editBody.trim()) return
    updateMut.mutate(
      { id, patch: { title: editTitle.trim(), body: editBody.trim() } },
      { onSuccess: () => setEditingId(null) },
    )
  }

  const enabledCount = instructions.filter(i => i.enabled).length

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
          <NewCard
            title={newTitle}
            body={newBody}
            onTitleChange={setNewTitle}
            onBodyChange={setNewBody}
            onSave={handleCreate}
            onCancel={() => { setShowNew(false); setNewTitle(''); setNewBody('') }}
            saving={createMut.isPending}
          />
        )}

        {instructions.map(inst =>
          editingId === inst.id ? (
            <EditCard
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
        <button
          onClick={onDelete}
          className="text-[11px] font-mono px-2 py-0.5 rounded-[5px] transition-all"
          style={{ color: 'var(--red)', background: 'var(--red-bg)' }}
        >
          delete
        </button>
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

function NewCard({
  title, body, onTitleChange, onBodyChange, onSave, onCancel, saving,
}: {
  title: string; body: string
  onTitleChange: (v: string) => void; onBodyChange: (v: string) => void
  onSave: () => void; onCancel: () => void; saving: boolean
}) {
  return (
    <div
      className="rounded-[10px] p-4 flex flex-col gap-3"
      style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-focus)' }}
    >
      <input
        autoFocus
        placeholder="Title (e.g. Opencode tab rename)"
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
        placeholder="Instruction (e.g. When Microsoft Edge tab title contains 'Opencode', classify the app_name as 'Opencode')"
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

function EditCard({
  title, body, onTitleChange, onBodyChange, onSave, onCancel, saving,
}: {
  title: string; body: string
  onTitleChange: (v: string) => void; onBodyChange: (v: string) => void
  onSave: () => void; onCancel: () => void; saving: boolean
}) {
  return (
    <div
      className="rounded-[10px] p-4 flex flex-col gap-3"
      style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-focus)' }}
    >
      <input
        autoFocus
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
