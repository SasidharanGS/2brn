import { useEffect, useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Plugin, PluginRule, PluginTool, RuleExecution } from '../api/types'
import { queryKeys } from '../api/queryKeys'
import { parseArgs, parseEnv } from '../lib/pluginInput'

const PLUGINS_QK = queryKeys.plugins()
const RULES_QK = queryKeys.pluginRules
const TOOLS_QK = queryKeys.pluginTools
const EXEC_QK = queryKeys.ruleExecutions

/** Plugin list + selection state (auto-selects the first plugin on load). */
export function usePluginsList() {
  const qc = useQueryClient()
  const { data: plugins = [], isLoading } = useQuery<Plugin[]>({
    queryKey: PLUGINS_QK,
    queryFn: api.listPlugins,
    refetchInterval: 15_000,
  })

  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [showNewPlugin, setShowNewPlugin] = useState(false)

  // Auto-select the first plugin once they load
  useEffect(() => {
    if (selectedId === null && plugins.length > 0) {
      setSelectedId(plugins[0].id)
    }
  }, [plugins, selectedId])

  const selected = useMemo(
    () => plugins.find(p => p.id === selectedId) ?? null,
    [plugins, selectedId],
  )

  const invalidatePlugins = () => qc.invalidateQueries({ queryKey: PLUGINS_QK })

  return {
    plugins, isLoading,
    selectedId, setSelectedId, selected,
    showNewPlugin, setShowNewPlugin,
    invalidatePlugins,
  }
}

/** New-plugin form state + create mutation (args/env parsed from textarea text). */
export function useNewPluginForm(onCreated: (p: Plugin) => void) {
  const [name, setName] = useState('')
  const [command, setCommand] = useState('')
  const [argsText, setArgsText] = useState('')
  const [envText, setEnvText] = useState('')
  const [error, setError] = useState<string | null>(null)

  const createMut = useMutation({
    mutationFn: api.createPlugin,
  })

  async function handleSave() {
    setError(null)
    if (!name.trim() || !command.trim()) {
      setError('Name and command are required')
      return
    }
    try {
      const plugin = await createMut.mutateAsync({
        name: name.trim(),
        command: command.trim(),
        args: parseArgs(argsText),
        env: parseEnv(envText),
      })
      onCreated(plugin)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create plugin')
    }
  }

  return {
    name, setName, command, setCommand,
    argsText, setArgsText, envText, setEnvText,
    error, saving: createMut.isPending, handleSave,
  }
}

/** Rules + tools for one plugin, plus enable-toggle and delete mutations. */
export function usePluginDetail(plugin: Plugin, onDeleted: () => void) {
  const qc = useQueryClient()
  const { data: rules = [] } = useQuery<PluginRule[]>({
    queryKey: RULES_QK(plugin.id),
    queryFn: () => api.listPluginRules(plugin.id),
  })
  const { data: tools = [] } = useQuery<PluginTool[]>({
    queryKey: TOOLS_QK(plugin.id),
    queryFn: () => api.listPluginTools(plugin.id),
    retry: 0,
  })

  const togglePluginMut = useMutation({
    mutationFn: () => api.updatePlugin(plugin.id, { enabled: !plugin.enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: PLUGINS_QK }),
  })

  const deletePluginMut = useMutation({
    mutationFn: () => api.deletePlugin(plugin.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: PLUGINS_QK })
      onDeleted()
    },
  })

  const invalidateRules = () => qc.invalidateQueries({ queryKey: RULES_QK(plugin.id) })

  return { rules, tools, togglePluginMut, deletePluginMut, invalidateRules }
}

/** Per-rule mutations: enable-toggle, re-parse, run-now, delete. */
export function useRuleActions(rule: PluginRule) {
  const qc = useQueryClient()
  const toggleMut = useMutation({
    mutationFn: () => api.updatePluginRule(rule.id, { enabled: !rule.enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: RULES_QK(rule.plugin_id) }),
  })
  const reparseMut = useMutation({
    mutationFn: () => api.reparsePluginRule(rule.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: RULES_QK(rule.plugin_id) }),
  })
  const runMut = useMutation({
    mutationFn: () => api.runPluginRule(rule.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: EXEC_QK(rule.id) }),
  })
  const deleteMut = useMutation({
    mutationFn: () => api.deletePluginRule(rule.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: RULES_QK(rule.plugin_id) }),
  })
  return { toggleMut, reparseMut, runMut, deleteMut }
}

/** Create/edit form state for a rule + the save flow. */
export function useRuleEditor(
  mode: 'create' | 'edit',
  pluginId: number,
  rule: PluginRule | undefined,
  onSaved: () => void,
) {
  const [title, setTitle] = useState(rule?.title ?? '')
  const [text, setText] = useState(rule?.rule_text ?? '')
  const [error, setError] = useState<string | null>(null)

  const createMut = useMutation({
    mutationFn: () => api.createPluginRule({
      plugin_id: pluginId,
      title: title.trim(),
      rule_text: text.trim(),
    }),
  })
  const updateMut = useMutation({
    mutationFn: () => api.updatePluginRule(rule!.id, {
      title: title.trim(),
      rule_text: text.trim(),
    }),
  })

  const saving = createMut.isPending || updateMut.isPending

  async function handleSave() {
    setError(null)
    if (!title.trim() || !text.trim()) {
      setError('Title and rule text are required')
      return
    }
    try {
      if (mode === 'create') {
        await createMut.mutateAsync()
      } else {
        await updateMut.mutateAsync()
      }
      onSaved()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed')
    }
  }

  return { title, setTitle, text, setText, error, saving, handleSave }
}

/** Last executions of a rule (auto-refreshing). */
export function useRuleExecutions(ruleId: number) {
  const { data: execs = [], isLoading } = useQuery<RuleExecution[]>({
    queryKey: EXEC_QK(ruleId),
    queryFn: () => api.listRuleExecutions(ruleId, 10),
    refetchInterval: 5_000,
  })
  return { execs, isLoading }
}
