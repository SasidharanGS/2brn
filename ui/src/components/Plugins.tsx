import { useEffect, useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Plugin, PluginRule, PluginTool, RuleExecution } from '../api/types'
import Toggle from './shared/Toggle'

const PLUGINS_QK = ['plugins']
const RULES_QK = (id: number | null) => ['plugin-rules', id ?? 0]
const TOOLS_QK = (id: number | null) => ['plugin-tools', id ?? 0]
const EXEC_QK = (id: number | null) => ['rule-executions', id ?? 0]


export default function Plugins() {
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

  return (
    <div className="flex h-full overflow-hidden">
      {/* ── Left pane: plugin list ──────────────────────────────────────── */}
      <aside
        className="flex flex-col w-[260px] shrink-0 border-r overflow-hidden"
        style={{ borderColor: 'var(--border)', background: 'var(--bg-surface)' }}
      >
        <div
          className="flex items-center justify-between px-4 py-3 border-b shrink-0"
          style={{ borderColor: 'var(--border)' }}
        >
          <div>
            <h2 className="text-[13px] font-semibold" style={{ color: 'var(--text)' }}>
              Plugins
            </h2>
            <p className="text-[10px] mt-0.5" style={{ color: 'var(--text-dim)' }}>
              {plugins.length === 0 ? 'No plugins' : `${plugins.length} configured`}
            </p>
          </div>
          <button
            onClick={() => setShowNewPlugin(true)}
            className="text-[11px] font-mono px-2 py-1 rounded-[6px] transition-all"
            style={{
              background: 'var(--accent-glow)',
              color: 'var(--accent)',
              border: '1px solid var(--border-focus)',
            }}
          >
            + add
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2 flex flex-col gap-1">
          {isLoading && (
            <p className="text-[11px] px-2 py-2" style={{ color: 'var(--text-dim) ' }}>Loading…</p>
          )}
          {plugins.map(p => (
            <PluginListItem
              key={p.id}
              plugin={p}
              active={p.id === selectedId}
              onSelect={() => setSelectedId(p.id)}
            />
          ))}
          {!isLoading && plugins.length === 0 && !showNewPlugin && (
            <div className="px-3 py-6 text-center">
              <p className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                No plugins yet. Add an MCP server to give 2brn new abilities.
              </p>
            </div>
          )}
        </div>
      </aside>

      {/* ── Right pane: rules / details ─────────────────────────────────── */}
      <section className="flex-1 min-w-0 overflow-hidden flex flex-col">
        {showNewPlugin ? (
          <NewPluginForm
            onCancel={() => setShowNewPlugin(false)}
            onCreated={(p) => {
              setShowNewPlugin(false)
              setSelectedId(p.id)
              qc.invalidateQueries({ queryKey: PLUGINS_QK })
            }}
          />
        ) : selected ? (
          <PluginDetail plugin={selected} onDeleted={() => setSelectedId(null)} />
        ) : (
          <EmptyState />
        )}
      </section>
    </div>
  )
}


// ────────────────────────────────────────────────────────────────────────────
// Plugin list item
// ────────────────────────────────────────────────────────────────────────────

function PluginListItem({
  plugin, active, onSelect,
}: { plugin: Plugin; active: boolean; onSelect: () => void }) {
  const healthColor = plugin.last_health_ok === null
    ? 'var(--text-dim)'
    : plugin.last_health_ok
      ? '#22c55e'
      : 'var(--red)'

  return (
    <button
      onClick={onSelect}
      className="text-left px-3 py-2 rounded-[8px] transition-all flex items-center gap-2"
      style={active
        ? { background: 'var(--accent-glow)', border: '1px solid var(--border-focus)' }
        : { background: 'transparent', border: '1px solid transparent' }
      }
    >
      <span
        className="shrink-0 rounded-full"
        style={{ width: 8, height: 8, background: healthColor }}
        title={plugin.last_health_error ?? (plugin.last_health_ok ? 'healthy' : 'unknown')}
      />
      <div className="flex-1 min-w-0">
        <div
          className="text-[12px] font-medium truncate"
          style={{
            color: active ? 'var(--text)' : 'var(--text-muted)',
            opacity: plugin.enabled ? 1 : 0.5,
          }}
        >
          {plugin.name}
        </div>
        <div
          className="text-[10px] font-mono truncate"
          style={{ color: 'var(--text-dim)' }}
        >
          {plugin.command}{plugin.args.length > 0 && ' …'}
        </div>
      </div>
    </button>
  )
}


// ────────────────────────────────────────────────────────────────────────────
// New plugin form
// ────────────────────────────────────────────────────────────────────────────

function NewPluginForm({
  onCancel, onCreated,
}: { onCancel: () => void; onCreated: (p: Plugin) => void }) {
  const [name, setName] = useState('')
  const [command, setCommand] = useState('')
  const [argsText, setArgsText] = useState('')
  const [envText, setEnvText] = useState('')
  const [error, setError] = useState<string | null>(null)

  const createMut = useMutation({
    mutationFn: api.createPlugin,
  })

  function parseArgs(text: string): string[] {
    return text.trim().length === 0
      ? []
      : text.split('\n').map(s => s.trim()).filter(Boolean)
  }

  function parseEnv(text: string): Record<string, string> {
    const out: Record<string, string> = {}
    text.split('\n').forEach(line => {
      const trimmed = line.trim()
      if (!trimmed || trimmed.startsWith('#')) return
      const eq = trimmed.indexOf('=')
      if (eq <= 0) return
      const key = trimmed.slice(0, eq).trim()
      const value = trimmed.slice(eq + 1).trim()
      if (key) out[key] = value
    })
    return out
  }

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

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-2xl mx-auto flex flex-col gap-4">
        <div>
          <h1 className="text-[16px] font-semibold" style={{ color: 'var(--text)' }}>
            Add a plugin
          </h1>
          <p className="text-[12px] mt-1" style={{ color: 'var(--text-dim)' }}>
            Plugins are MCP servers — local commands 2brn launches over stdio. Once a plugin is
            added, you can write natural-language rules that call its tools.
          </p>
        </div>

        <Field label="Name">
          <input
            autoFocus
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="joplin"
            className="w-full text-[13px] px-3 py-2 rounded-[7px] outline-none"
            style={{ background: 'var(--bg-input)', border: '1px solid var(--border-2)', color: 'var(--text)' }}
          />
          <Hint>Internal identifier. Lowercase, no spaces. Used as keychain namespace.</Hint>
        </Field>

        <Field label="Command">
          <input
            value={command}
            onChange={e => setCommand(e.target.value)}
            placeholder="node"
            className="w-full text-[13px] px-3 py-2 rounded-[7px] outline-none font-mono"
            style={{ background: 'var(--bg-input)', border: '1px solid var(--border-2)', color: 'var(--text)' }}
          />
          <Hint>Executable to launch (e.g. <code>node</code>, <code>python</code>, <code>/usr/local/bin/foo</code>).</Hint>
        </Field>

        <Field label="Arguments (one per line)">
          <textarea
            value={argsText}
            onChange={e => setArgsText(e.target.value)}
            rows={3}
            placeholder={'/Users/me/tools/joplin-mcp-server/dist/index.js'}
            className="w-full text-[12px] px-3 py-2 rounded-[7px] outline-none resize-none font-mono"
            style={{ background: 'var(--bg-input)', border: '1px solid var(--border-2)', color: 'var(--text)' }}
          />
        </Field>

        <Field label="Environment variables (KEY=value, one per line)">
          <textarea
            value={envText}
            onChange={e => setEnvText(e.target.value)}
            rows={3}
            placeholder={'JOPLIN_TOKEN=...\nJOPLIN_PORT=41184'}
            className="w-full text-[12px] px-3 py-2 rounded-[7px] outline-none resize-none font-mono"
            style={{ background: 'var(--bg-input)', border: '1px solid var(--border-2)', color: 'var(--text)' }}
          />
          <Hint>Values are stored in the OS keychain. Only the key names persist in 2brn's database.</Hint>
        </Field>

        {error && (
          <div className="text-[12px] px-3 py-2 rounded-[7px]"
               style={{ background: 'var(--red-bg)', color: 'var(--red)' }}>
            {error}
          </div>
        )}

        <div className="flex gap-2 justify-end pt-2">
          <button
            onClick={onCancel}
            className="text-[12px] px-3 py-1.5 rounded-[7px] transition-all"
            style={{ color: 'var(--text-dim)', background: 'var(--bg-surface-2)' }}
          >
            cancel
          </button>
          <button
            onClick={handleSave}
            disabled={createMut.isPending}
            className="text-[12px] px-3 py-1.5 rounded-[7px] font-medium transition-all disabled:opacity-40"
            style={{ background: 'var(--accent-glow)', color: 'var(--accent)', border: '1px solid var(--border-focus)' }}
          >
            {createMut.isPending ? 'saving…' : 'add plugin'}
          </button>
        </div>
      </div>
    </div>
  )
}


// ────────────────────────────────────────────────────────────────────────────
// Plugin detail (rules)
// ────────────────────────────────────────────────────────────────────────────

function PluginDetail({ plugin, onDeleted }: { plugin: Plugin; onDeleted: () => void }) {
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

  const [showNewRule, setShowNewRule] = useState(false)
  const [editingRuleId, setEditingRuleId] = useState<number | null>(null)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

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

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b shrink-0" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="text-[18px] font-semibold truncate" style={{ color: 'var(--text)' }}>
                {plugin.name}
              </h1>
              {plugin.last_health_ok === false && (
                <span
                  className="text-[10px] font-mono px-1.5 py-0.5 rounded"
                  style={{ background: 'var(--red-bg)', color: 'var(--red)' }}
                  title={plugin.last_health_error ?? 'unknown error'}
                >
                  error
                </span>
              )}
              {plugin.last_health_ok === true && (
                <span
                  className="text-[10px] font-mono px-1.5 py-0.5 rounded"
                  style={{ background: 'rgba(34,197,94,0.12)', color: '#22c55e' }}
                >
                  healthy
                </span>
              )}
            </div>
            <p className="text-[11px] mt-1 font-mono truncate" style={{ color: 'var(--text-dim)' }}>
              {plugin.command} {plugin.args.join(' ')}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Toggle enabled={plugin.enabled} onToggle={() => togglePluginMut.mutate()} />
            <button
              onClick={() => setShowAdvanced(v => !v)}
              className="text-[11px] font-mono px-2 py-1 rounded-[5px]"
              style={{ color: 'var(--text-dim)', background: 'var(--bg-surface-2)' }}
            >
              {showAdvanced ? 'hide' : 'config'}
            </button>
          </div>
        </div>
        {plugin.last_health_error && (
          <p className="mt-2 text-[11px] font-mono" style={{ color: 'var(--red)' }}>
            {plugin.last_health_error}
          </p>
        )}
      </div>

      {/* Advanced section */}
      {showAdvanced && (
        <div
          className="px-6 py-4 border-b shrink-0 flex flex-col gap-3"
          style={{ borderColor: 'var(--border)', background: 'var(--bg-surface)' }}
        >
          <div>
            <p className="text-[11px]" style={{ color: 'var(--text-dim)' }}>Environment keys</p>
            <p className="text-[12px] font-mono mt-1" style={{ color: 'var(--text-muted)' }}>
              {plugin.env_keys.length === 0 ? '(none)' : plugin.env_keys.join(', ')}
            </p>
          </div>
          <div>
            <p className="text-[11px]" style={{ color: 'var(--text-dim)' }}>Available tools</p>
            <p className="text-[12px] font-mono mt-1" style={{ color: 'var(--text-muted)' }}>
              {tools.length === 0 ? '(loading or unavailable)' : tools.map(t => t.name).join(', ')}
            </p>
          </div>
          {confirmDelete ? (
            <div className="flex items-center gap-2">
              <span className="text-[11px]" style={{ color: 'var(--red)' }}>
                Delete this plugin and all its rules?
              </span>
              <button
                onClick={() => deletePluginMut.mutate()}
                className="text-[11px] px-2 py-1 rounded-[5px] font-medium"
                style={{ background: 'var(--red)', color: '#fff' }}
              >
                yes, delete
              </button>
              <button
                onClick={() => setConfirmDelete(false)}
                className="text-[11px] px-2 py-1 rounded-[5px]"
                style={{ color: 'var(--text-dim)', background: 'var(--bg-surface-2)' }}
              >
                cancel
              </button>
            </div>
          ) : (
            <button
              onClick={() => setConfirmDelete(true)}
              className="text-[11px] px-2 py-1 rounded-[5px] self-start"
              style={{ background: 'var(--red-bg)', color: 'var(--red)' }}
            >
              delete plugin
            </button>
          )}
        </div>
      )}

      {/* Rules */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-[13px] font-medium" style={{ color: 'var(--text)' }}>Rules</h2>
            <p className="text-[11px] mt-0.5" style={{ color: 'var(--text-dim)' }}>
              Plain-English instructions that turn into MCP tool calls when events fire.
            </p>
          </div>
          <button
            onClick={() => { setShowNewRule(true); setEditingRuleId(null) }}
            className="text-[11px] font-mono px-2 py-1 rounded-[6px]"
            style={{
              background: 'var(--accent-glow)',
              color: 'var(--accent)',
              border: '1px solid var(--border-focus)',
            }}
          >
            + new rule
          </button>
        </div>

        <div className="flex flex-col gap-2">
          {showNewRule && (
            <RuleEditor
              mode="create"
              pluginId={plugin.id}
              onCancel={() => setShowNewRule(false)}
              onSaved={() => {
                setShowNewRule(false)
                qc.invalidateQueries({ queryKey: RULES_QK(plugin.id) })
              }}
            />
          )}

          {rules.map(rule =>
            editingRuleId === rule.id ? (
              <RuleEditor
                key={rule.id}
                mode="edit"
                pluginId={plugin.id}
                rule={rule}
                onCancel={() => setEditingRuleId(null)}
                onSaved={() => {
                  setEditingRuleId(null)
                  qc.invalidateQueries({ queryKey: RULES_QK(plugin.id) })
                }}
              />
            ) : (
              <RuleCard
                key={rule.id}
                rule={rule}
                onEdit={() => setEditingRuleId(rule.id)}
              />
            )
          )}

          {!showNewRule && rules.length === 0 && (
            <div
              className="flex flex-col items-center justify-center py-12 gap-2 rounded-[10px]"
              style={{ border: '1px dashed var(--border-2)' }}
            >
              <p className="text-[12px]" style={{ color: 'var(--text-muted)' }}>
                No rules yet.
              </p>
              <p className="text-[11px] font-mono max-w-md text-center" style={{ color: 'var(--text-dim)' }}>
                Example: "When my journal is generated, append it to the Journal note in Joplin."
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}


// ────────────────────────────────────────────────────────────────────────────
// Rule card + editor
// ────────────────────────────────────────────────────────────────────────────

function RuleCard({ rule, onEdit }: { rule: PluginRule; onEdit: () => void }) {
  const qc = useQueryClient()
  const [showExec, setShowExec] = useState(false)

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

  const parseBadge = (() => {
    if (rule.parse_status === 'ok') {
      return { label: rule.trigger || 'ready', bg: 'rgba(34,197,94,0.12)', fg: '#22c55e' }
    }
    if (rule.parse_status === 'error') {
      return { label: 'parse error', bg: 'var(--red-bg)', fg: 'var(--red)' }
    }
    return { label: 'parsing…', bg: 'var(--bg-surface-2)', fg: 'var(--text-dim)' }
  })()

  return (
    <div
      className="rounded-[10px] p-4 flex flex-col gap-2"
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border-2)',
        opacity: rule.enabled ? 1 : 0.55,
      }}
    >
      <div className="flex items-center gap-3">
        <Toggle enabled={rule.enabled} onToggle={() => toggleMut.mutate()} />
        <span className="flex-1 text-[13px] font-medium truncate" style={{ color: 'var(--text)' }}>
          {rule.title}
        </span>
        <span
          className="text-[10px] font-mono px-1.5 py-0.5 rounded shrink-0"
          style={{ background: parseBadge.bg, color: parseBadge.fg }}
          title={rule.parse_error ?? undefined}
        >
          {parseBadge.label}
        </span>
        {rule.tool_name && (
          <span
            className="text-[10px] font-mono px-1.5 py-0.5 rounded shrink-0"
            style={{ background: 'var(--bg-surface-2)', color: 'var(--text-dim)' }}
          >
            → {rule.tool_name}
          </span>
        )}
      </div>

      <p
        className="text-[12px] leading-relaxed pl-[44px]"
        style={{ color: 'var(--text-muted)', whiteSpace: 'pre-wrap' }}
      >
        {rule.rule_text}
      </p>

      {rule.parse_error && (
        <p className="text-[11px] pl-[44px] font-mono" style={{ color: 'var(--red)' }}>
          {rule.parse_error}
        </p>
      )}

      <div className="flex gap-2 justify-end mt-1">
        <button
          onClick={() => setShowExec(v => !v)}
          className="text-[11px] font-mono px-2 py-0.5 rounded-[5px]"
          style={{ color: 'var(--text-dim)', background: 'var(--bg-surface-2)' }}
        >
          {showExec ? 'hide history' : 'history'}
        </button>
        <button
          onClick={() => runMut.mutate()}
          disabled={rule.parse_status !== 'ok' || runMut.isPending}
          className="text-[11px] font-mono px-2 py-0.5 rounded-[5px] disabled:opacity-40"
          style={{ color: 'var(--accent)', background: 'var(--accent-glow)' }}
        >
          {runMut.isPending ? 'running…' : 'run now'}
        </button>
        <button
          onClick={() => reparseMut.mutate()}
          disabled={reparseMut.isPending}
          className="text-[11px] font-mono px-2 py-0.5 rounded-[5px] disabled:opacity-40"
          style={{ color: 'var(--text-dim)', background: 'var(--bg-surface-2)' }}
        >
          re-parse
        </button>
        <button
          onClick={onEdit}
          className="text-[11px] font-mono px-2 py-0.5 rounded-[5px]"
          style={{ color: 'var(--text-dim)', background: 'var(--bg-surface-2)' }}
        >
          edit
        </button>
        <button
          onClick={() => { if (confirm(`Delete rule "${rule.title}"?`)) deleteMut.mutate() }}
          className="text-[11px] font-mono px-2 py-0.5 rounded-[5px]"
          style={{ color: 'var(--red)', background: 'var(--red-bg)' }}
        >
          delete
        </button>
      </div>

      {showExec && <ExecutionHistory ruleId={rule.id} />}
    </div>
  )
}


function RuleEditor({
  mode, pluginId, rule, onCancel, onSaved,
}: {
  mode: 'create' | 'edit'
  pluginId: number
  rule?: PluginRule
  onCancel: () => void
  onSaved: () => void
}) {
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

  return (
    <div
      className="rounded-[10px] p-4 flex flex-col gap-3"
      style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-focus)' }}
    >
      <input
        autoFocus
        value={title}
        onChange={e => setTitle(e.target.value)}
        placeholder="Rule title (e.g. Mirror journal to Joplin)"
        className="w-full text-[13px] px-3 py-2 rounded-[7px] outline-none"
        style={{ background: 'var(--bg-input)', border: '1px solid var(--border-2)', color: 'var(--text)' }}
      />
      <textarea
        value={text}
        onChange={e => setText(e.target.value)}
        rows={4}
        placeholder={'When my journal is generated, create a Joplin note in the "Journal" notebook titled with today\'s date and the journal content as the body.'}
        className="w-full text-[12px] px-3 py-2 rounded-[7px] outline-none resize-none leading-relaxed"
        style={{ background: 'var(--bg-input)', border: '1px solid var(--border-2)', color: 'var(--text)' }}
      />
      <p className="text-[10px] font-mono" style={{ color: 'var(--text-dim)' }}>
        Triggers you can use: <code>journal_generated</code>, <code>blog_generated</code>,
        <code> capture_inferred</code>, <code>daily_at_HH:MM</code>, <code>every_Xs</code>, <code>manual</code>.
        Placeholders: <code>{'{date}'}</code>, <code>{'{journal_content}'}</code>, <code>{'{blog_content}'}</code>,
        <code> {'{summary}'}</code>, <code>{'{task_category}'}</code>, <code>{'{app_name}'}</code>.
      </p>

      {error && (
        <div className="text-[11px] px-2 py-1.5 rounded-[6px]"
             style={{ background: 'var(--red-bg)', color: 'var(--red)' }}>
          {error}
        </div>
      )}

      <div className="flex gap-2 justify-end">
        <button
          onClick={onCancel}
          className="text-[12px] px-3 py-1.5 rounded-[7px]"
          style={{ color: 'var(--text-dim)', background: 'var(--bg-surface-2)' }}
        >
          cancel
        </button>
        <button
          onClick={handleSave}
          disabled={saving}
          className="text-[12px] px-3 py-1.5 rounded-[7px] font-medium disabled:opacity-40"
          style={{ background: 'var(--accent-glow)', color: 'var(--accent)', border: '1px solid var(--border-focus)' }}
        >
          {saving ? 'parsing…' : mode === 'create' ? 'save rule' : 'save'}
        </button>
      </div>
    </div>
  )
}


// ────────────────────────────────────────────────────────────────────────────
// Execution history
// ────────────────────────────────────────────────────────────────────────────

function ExecutionHistory({ ruleId }: { ruleId: number }) {
  const { data: execs = [], isLoading } = useQuery<RuleExecution[]>({
    queryKey: EXEC_QK(ruleId),
    queryFn: () => api.listRuleExecutions(ruleId, 10),
    refetchInterval: 5_000,
  })

  if (isLoading) {
    return <p className="text-[11px] pl-[44px]" style={{ color: 'var(--text-dim)' }}>Loading history…</p>
  }
  if (execs.length === 0) {
    return <p className="text-[11px] pl-[44px]" style={{ color: 'var(--text-dim)' }}>No runs yet.</p>
  }

  return (
    <div className="pl-[44px] mt-1 flex flex-col gap-1">
      {execs.map(e => (
        <div
          key={e.id}
          className="text-[11px] font-mono px-2 py-1.5 rounded-[6px] flex items-start gap-2"
          style={{ background: 'var(--bg-surface-2)' }}
        >
          <span
            className="shrink-0 px-1 rounded"
            style={{
              background: e.status === 'ok' ? 'rgba(34,197,94,0.12)' : 'var(--red-bg)',
              color: e.status === 'ok' ? '#22c55e' : 'var(--red)',
            }}
          >
            {e.status}
          </span>
          <span style={{ color: 'var(--text-dim)' }}>{e.started_at.replace('T', ' ').slice(0, 19)}</span>
          {e.error && (
            <span className="truncate" style={{ color: 'var(--red)' }} title={e.error}>
              {e.error}
            </span>
          )}
        </div>
      ))}
    </div>
  )
}


// ────────────────────────────────────────────────────────────────────────────
// Shared UI bits
// ────────────────────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex flex-1 items-center justify-center px-8">
      <div className="max-w-md text-center flex flex-col gap-3">
        <span className="text-[32px]">🔌</span>
        <h2 className="text-[15px] font-semibold" style={{ color: 'var(--text)' }}>
          Plugins extend 2brn with MCP servers
        </h2>
        <p className="text-[12px]" style={{ color: 'var(--text-muted)' }}>
          Add a Model Context Protocol server (Joplin, Notion, Slack, anything) and write
          natural-language rules that fire when events happen — like "when my journal is
          generated, save it to Joplin".
        </p>
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-[11px] font-medium" style={{ color: 'var(--text-dim)' }}>{label}</span>
      {children}
    </label>
  )
}

function Hint({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[10px]" style={{ color: 'var(--text-dim)' }}>
      {children}
    </p>
  )
}


