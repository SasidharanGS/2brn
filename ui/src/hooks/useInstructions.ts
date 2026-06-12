import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { UserInstruction } from '../api/types'
import { queryKeys } from '../api/queryKeys'

/** Instructions list + CRUD mutations + new/edit form state. */
export function useInstructions() {
  const qc = useQueryClient()
  const { data: instructions = [], isLoading } = useQuery({
    queryKey: queryKeys.instructions(),
    queryFn: api.listInstructions,
  })

  const createMut = useMutation({
    mutationFn: ({ title, body }: { title: string; body: string }) =>
      api.createInstruction(title, body, true),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.instructions() }),
  })
  const updateMut = useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: Partial<Pick<UserInstruction, 'title' | 'body' | 'enabled'>> }) =>
      api.updateInstruction(id, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.instructions() }),
  })
  const deleteMut = useMutation({
    mutationFn: (id: number) => api.deleteInstruction(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.instructions() }),
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

  return {
    instructions, isLoading, enabledCount,
    createMut, updateMut, deleteMut,
    showNew, setShowNew,
    newTitle, setNewTitle, newBody, setNewBody,
    editingId, setEditingId, editTitle, setEditTitle, editBody, setEditBody,
    handleCreate, startEdit, handleSaveEdit,
  }
}
