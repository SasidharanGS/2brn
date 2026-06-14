import { useState, type CSSProperties } from 'react'
import type { Plugin, PluginRule } from '../api/types'
import {
  usePluginsList, useNewPluginForm, usePluginDetail,
  useRuleActions, useRuleEditor, useRuleExecutions,
} from '../hooks/usePlugins'
import { Switch, Button, QuietButton, Badge, Field, Input, EmptyState, SectionLabel, Icon } from '../ui-kit'

// Unified Plugins — one master-detail component for both skins. All state lives
// in the usePlugins hooks; the tree is token-driven (status colours come from
// --k-health-* / Badge tones).
const monoArea: CSSProperties = {
  width: '100%', boxSizing: 'border-box', resize: 'vertical', fontFamily: 'var(--k-font-mono)',
  lineHeight: 1.5, fontSize: 'var(--k-text-sm)',
}

export default function Plugins() {
  const { plugins, isLoading, selectedId, setSelectedId, selected, showNewPlugin, setShowNewPlugin, invalidatePlugins } = usePluginsList()

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '250px 1fr', height: '100%' }}>
      <aside style={{ borderRight: '1px solid var(--k-rule)', padding: 'var(--k-space-md)', overflowY: 'auto', minHeight: 0, display: 'flex', flexDirection: 'column', gap: 'var(--k-space-sm)' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 'var(--k-space-sm)' }}>
          <div>
            <div style={{ fontSize: 'var(--k-text-title)', color: 'var(--k-fg)', fontWeight: 'var(--k-emphasis-weight)' as CSSProperties['fontWeight'], textTransform: 'var(--k-text-transform)' as CSSProperties['textTransform'] }}>Plugins</div>
            <div className="k-field-hint" style={{ marginTop: 2 }}>{plugins.length === 0 ? 'No plugins' : `${plugins.length} configured`}</div>
          </div>
          <Button variant="soft" onClick={() => setShowNewPlugin(true)}><Icon name="plus" size={12} />Add</Button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {isLoading && <div className="k-field-hint" style={{ marginTop: 0 }}>Loading…</div>}
          {plugins.map(p => <PluginListItem key={p.id} plugin={p} active={p.id === selectedId} onSelect={() => setSelectedId(p.id)} />)}
          {!isLoading && plugins.length === 0 && !showNewPlugin && (
            <p className="k-field-hint" style={{ marginTop: 'var(--k-space-sm)' }}>No plugins yet. Add an MCP server to give 2brn new abilities.</p>
          )}
        </div>
      </aside>

      <section style={{ minWidth: 0, minHeight: 0, overflowY: 'auto' }}>
        {showNewPlugin ? (
          <NewPluginForm onCancel={() => setShowNewPlugin(false)} onCreated={p => { setShowNewPlugin(false); setSelectedId(p.id); invalidatePlugins() }} />
        ) : selected ? (
          <PluginDetail plugin={selected} onDeleted={() => setSelectedId(null)} />
        ) : (
          <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'var(--k-space-lg)' }}>
            <EmptyState icon="plugins" title="Plugins extend 2brn with MCP servers">
              Add a Model Context Protocol server (Joplin, Notion, Slack, anything) and write
              natural-language rules that fire when events happen — like "when my journal is generated, save it to Joplin".
            </EmptyState>
          </div>
        )}
      </section>
    </div>
  )
}

function PluginListItem({ plugin, active, onSelect }: { plugin: Plugin; active: boolean; onSelect: () => void }) {
  const dot = plugin.last_health_ok === null ? 'var(--k-rule)' : plugin.last_health_ok ? 'var(--k-health-ok)' : 'var(--k-health-err)'
  return (
    <button onClick={onSelect} style={{
      textAlign: 'left', background: active ? 'var(--k-accent-soft)' : 'transparent', border: 'none',
      borderRadius: 'var(--k-radius-sm)', padding: '6px 8px', cursor: 'pointer', width: '100%',
      display: 'flex', flexDirection: 'column', gap: 2, fontFamily: 'var(--k-font)', opacity: plugin.enabled ? 1 : 0.55,
    }}>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontSize: 'var(--k-text-sm)', color: active ? 'var(--k-fg)' : 'var(--k-muted)' }}>
        <span style={{ width: 6, height: 6, borderRadius: '50%', flex: '0 0 auto', background: dot }} title={plugin.last_health_error ?? (plugin.last_health_ok ? 'healthy' : 'unknown')} />
        {plugin.name}
      </span>
      <span style={{ fontSize: 'var(--k-text-meta)', fontFamily: 'var(--k-font-mono)', color: 'var(--k-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '100%' }}>
        {plugin.command}{plugin.args.length > 0 && ' …'}
      </span>
    </button>
  )
}

function NewPluginForm({ onCancel, onCreated }: { onCancel: () => void; onCreated: (p: Plugin) => void }) {
  const { name, setName, command, setCommand, argsText, setArgsText, envText, setEnvText, error, saving, handleSave } = useNewPluginForm(onCreated)
  return (
    <div style={{ padding: 'var(--k-space-lg)' }}>
      <div style={{ maxWidth: 640, display: 'flex', flexDirection: 'column', gap: 'var(--k-space-md)' }}>
        <div>
          <div style={{ fontSize: 'var(--k-text-xl)', color: 'var(--k-fg)', fontWeight: 'var(--k-heading-weight)' as CSSProperties['fontWeight'], textTransform: 'var(--k-text-transform)' as CSSProperties['textTransform'] }}>Add a plugin</div>
          <p className="k-field-hint">Plugins are MCP servers — local commands 2brn launches over stdio. Once added, you can write natural-language rules that call its tools.</p>
        </div>
        <Field label="Name" hint="Internal identifier. Lowercase, no spaces. Used as keychain namespace.">
          <Input autoFocus value={name} onChange={e => setName(e.target.value)} placeholder="joplin" />
        </Field>
        <Field label="Command" hint="Executable to launch (e.g. node, python, /usr/local/bin/foo).">
          <Input value={command} onChange={e => setCommand(e.target.value)} placeholder="node" style={{ fontFamily: 'var(--k-font-mono)' }} />
        </Field>
        <Field label="Arguments (one per line)">
          <textarea className="k-input" value={argsText} onChange={e => setArgsText(e.target.value)} rows={3} placeholder="/Users/me/tools/joplin-mcp-server/dist/index.js" style={monoArea} />
        </Field>
        <Field label="Environment variables (KEY=value, one per line)" hint="Values are stored in the OS keychain. Only the key names persist in 2brn's database.">
          <textarea className="k-input" value={envText} onChange={e => setEnvText(e.target.value)} rows={3} placeholder={'JOPLIN_TOKEN=...\nJOPLIN_PORT=41184'} style={monoArea} />
        </Field>
        {error && <div style={{ fontSize: 'var(--k-text-sm)', color: 'var(--k-danger)' }}>{error}</div>}
        <div style={{ display: 'flex', gap: 'var(--k-space-sm)', justifyContent: 'flex-end' }}>
          <Button onClick={onCancel}>Cancel</Button>
          <Button variant="soft" onClick={handleSave} disabled={saving}>{saving ? 'Saving…' : 'Add plugin'}</Button>
        </div>
      </div>
    </div>
  )
}

function PluginDetail({ plugin, onDeleted }: { plugin: Plugin; onDeleted: () => void }) {
  const { rules, tools, togglePluginMut, deletePluginMut, invalidateRules } = usePluginDetail(plugin, onDeleted)
  const [showNewRule, setShowNewRule] = useState(false)
  const [editingRuleId, setEditingRuleId] = useState<number | null>(null)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  return (
    <div style={{ padding: 'var(--k-space-lg)', display: 'flex', flexDirection: 'column', gap: 'var(--k-space-md)' }}>
      <div style={{ borderBottom: '1px solid var(--k-rule)', paddingBottom: 'var(--k-space-md)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--k-space-sm)' }}>
          <div style={{ minWidth: 0, display: 'flex', alignItems: 'center', gap: 'var(--k-space-sm)' }}>
            <span style={{ fontSize: 'var(--k-text-xl)', color: 'var(--k-fg)', fontWeight: 'var(--k-heading-weight)' as CSSProperties['fontWeight'], overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{plugin.name}</span>
            {plugin.last_health_ok === true && <Badge tone="ok">healthy</Badge>}
            {plugin.last_health_ok === false && <span title={plugin.last_health_error ?? 'unknown error'} style={{ fontSize: 'var(--k-text-label)', color: 'var(--k-health-err)', whiteSpace: 'nowrap' }}>error</span>}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--k-space-sm)', flex: '0 0 auto' }}>
            <Switch on={plugin.enabled} onToggle={() => togglePluginMut.mutate()} />
            <QuietButton onClick={() => setShowAdvanced(v => !v)}>{showAdvanced ? 'hide' : 'config'}</QuietButton>
          </div>
        </div>
        <p style={{ margin: '6px 0 0', fontSize: 'var(--k-text-meta)', fontFamily: 'var(--k-font-mono)', color: 'var(--k-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{plugin.command} {plugin.args.join(' ')}</p>
        {plugin.last_health_error && <p style={{ margin: '6px 0 0', fontSize: 'var(--k-text-meta)', fontFamily: 'var(--k-font-mono)', color: 'var(--k-health-err)' }}>{plugin.last_health_error}</p>}
      </div>

      {showAdvanced && (
        <div style={{ border: '1px solid var(--k-rule)', borderRadius: 'var(--k-radius)', padding: 'var(--k-space-md)', display: 'flex', flexDirection: 'column', gap: 'var(--k-space-sm)' }}>
          <div>
            <SectionLabel>Environment keys</SectionLabel>
            <p style={{ margin: '4px 0 0', fontSize: 'var(--k-text-sm)', fontFamily: 'var(--k-font-mono)', color: 'var(--k-muted)' }}>{plugin.env_keys.length === 0 ? '(none)' : plugin.env_keys.join(', ')}</p>
          </div>
          <div>
            <SectionLabel>Available tools</SectionLabel>
            <p style={{ margin: '4px 0 0', fontSize: 'var(--k-text-sm)', fontFamily: 'var(--k-font-mono)', color: 'var(--k-muted)' }}>{tools.length === 0 ? '(loading or unavailable)' : tools.map(t => t.name).join(', ')}</p>
          </div>
          {confirmDelete ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--k-space-sm)' }}>
              <span style={{ fontSize: 'var(--k-text-meta)', color: 'var(--k-health-err)' }}>Delete this plugin and all its rules?</span>
              <QuietButton danger onClick={() => deletePluginMut.mutate()}>yes, delete</QuietButton>
              <QuietButton onClick={() => setConfirmDelete(false)}>cancel</QuietButton>
            </div>
          ) : (
            <QuietButton danger onClick={() => setConfirmDelete(true)}>delete plugin</QuietButton>
          )}
        </div>
      )}

      <div>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 'var(--k-space-sm)' }}>
          <div>
            <SectionLabel>Rules</SectionLabel>
            <p className="k-field-hint" style={{ marginTop: 4 }}>Plain-English instructions that turn into MCP tool calls when events fire.</p>
          </div>
          <Button variant="soft" onClick={() => { setShowNewRule(true); setEditingRuleId(null) }}><Icon name="plus" size={12} />New rule</Button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--k-space-sm)' }}>
          {showNewRule && <RuleEditor mode="create" pluginId={plugin.id} onCancel={() => setShowNewRule(false)} onSaved={() => { setShowNewRule(false); invalidateRules() }} />}
          {rules.map(rule => editingRuleId === rule.id ? (
            <RuleEditor key={rule.id} mode="edit" pluginId={plugin.id} rule={rule} onCancel={() => setEditingRuleId(null)} onSaved={() => { setEditingRuleId(null); invalidateRules() }} />
          ) : (
            <RuleCard key={rule.id} rule={rule} onEdit={() => setEditingRuleId(rule.id)} />
          ))}
          {!showNewRule && rules.length === 0 && (
            <EmptyState dashed title="No rules yet.">
              <span style={{ fontFamily: 'var(--k-font-mono)', fontSize: 'var(--k-text-meta)' }}>Example: "when my journal is generated, append it to the Journal note in Joplin."</span>
            </EmptyState>
          )}
        </div>
      </div>
    </div>
  )
}

function RuleCard({ rule, onEdit }: { rule: PluginRule; onEdit: () => void }) {
  const [showExec, setShowExec] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const { toggleMut, reparseMut, runMut, deleteMut } = useRuleActions(rule)
  return (
    <div style={{ border: '1px solid var(--k-rule)', borderRadius: 'var(--k-radius)', padding: 'var(--k-space-md)', display: 'flex', flexDirection: 'column', gap: 'var(--k-space-sm)', opacity: rule.enabled ? 1 : 0.55 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--k-space-sm)' }}>
        <Switch on={rule.enabled} onToggle={() => toggleMut.mutate()} />
        <span style={{ flex: 1, minWidth: 0, fontSize: 'var(--k-text-title)', color: 'var(--k-fg)', fontWeight: 'var(--k-emphasis-weight)' as CSSProperties['fontWeight'], overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{rule.title}</span>
        {rule.parse_status === 'ok' && <Badge tone="ok">{rule.trigger || 'ready'}</Badge>}
        {rule.parse_status === 'error' && <span title={rule.parse_error ?? undefined} style={{ fontSize: 'var(--k-text-label)', color: 'var(--k-health-err)', whiteSpace: 'nowrap' }}>parse error</span>}
        {rule.parse_status !== 'ok' && rule.parse_status !== 'error' && <span style={{ fontSize: 'var(--k-text-label)', color: 'var(--k-muted)' }}>parsing…</span>}
        {rule.tool_name && <span style={{ fontSize: 'var(--k-text-label)', fontFamily: 'var(--k-font-mono)', color: 'var(--k-muted)', whiteSpace: 'nowrap' }}>→ {rule.tool_name}</span>}
      </div>
      <p style={{ margin: 0, paddingLeft: 46, fontSize: 'var(--k-text-body)', color: 'var(--k-muted)', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>{rule.rule_text}</p>
      {rule.parse_error && <p style={{ margin: 0, paddingLeft: 46, fontSize: 'var(--k-text-meta)', fontFamily: 'var(--k-font-mono)', color: 'var(--k-health-err)' }}>{rule.parse_error}</p>}
      <div style={{ display: 'flex', gap: 'var(--k-space-sm)', justifyContent: 'flex-end', alignItems: 'center' }}>
        <QuietButton onClick={() => setShowExec(v => !v)}>{showExec ? 'hide history' : 'history'}</QuietButton>
        <QuietButton accent disabled={rule.parse_status !== 'ok' || runMut.isPending} onClick={() => runMut.mutate()}>{runMut.isPending ? 'running…' : 'run now'}</QuietButton>
        <QuietButton disabled={reparseMut.isPending} onClick={() => reparseMut.mutate()}>re-parse</QuietButton>
        <QuietButton onClick={onEdit}>edit</QuietButton>
        {confirmDelete ? (
          <>
            <QuietButton danger onClick={() => { setConfirmDelete(false); deleteMut.mutate() }}>confirm</QuietButton>
            <QuietButton onClick={() => setConfirmDelete(false)}>cancel</QuietButton>
          </>
        ) : (
          <QuietButton danger onClick={() => setConfirmDelete(true)}>delete</QuietButton>
        )}
      </div>
      {showExec && <ExecutionHistory ruleId={rule.id} />}
    </div>
  )
}

function RuleEditor({ mode, pluginId, rule, onCancel, onSaved }: {
  mode: 'create' | 'edit'; pluginId: number; rule?: PluginRule; onCancel: () => void; onSaved: () => void
}) {
  const { title, setTitle, text, setText, error, saving, handleSave } = useRuleEditor(mode, pluginId, rule, onSaved)
  return (
    <div style={{ border: '1px solid var(--k-accent)', borderRadius: 'var(--k-radius)', padding: 'var(--k-space-md)', display: 'flex', flexDirection: 'column', gap: 'var(--k-space-sm)' }}>
      <Input autoFocus value={title} onChange={e => setTitle(e.target.value)} placeholder="Rule title (e.g. Mirror journal to Joplin)" />
      <textarea className="k-input" value={text} onChange={e => setText(e.target.value)} rows={4}
        placeholder={'When my journal is generated, create a Joplin note in the "Journal" notebook titled with today\'s date and the journal content as the body.'}
        style={{ width: '100%', boxSizing: 'border-box', resize: 'vertical', lineHeight: 1.6, fontSize: 'var(--k-text-sm)' }} />
      <p style={{ margin: 0, fontSize: 'var(--k-text-label)', fontFamily: 'var(--k-font-mono)', color: 'var(--k-muted)', lineHeight: 1.7 }}>
        Triggers: journal_generated · blog_generated · capture_inferred · daily_at_HH:MM · every_Xs · manual.
        Placeholders: {'{date}'} {'{journal_content}'} {'{blog_content}'} {'{summary}'} {'{task_category}'} {'{app_name}'}
      </p>
      {error && <div style={{ fontSize: 'var(--k-text-sm)', color: 'var(--k-danger)' }}>{error}</div>}
      <div style={{ display: 'flex', gap: 'var(--k-space-sm)', justifyContent: 'flex-end' }}>
        <Button onClick={onCancel}>Cancel</Button>
        <Button variant="soft" onClick={handleSave} disabled={saving}>{saving ? 'Parsing…' : mode === 'create' ? 'Save rule' : 'Save'}</Button>
      </div>
    </div>
  )
}

function ExecutionHistory({ ruleId }: { ruleId: number }) {
  const { execs, isLoading } = useRuleExecutions(ruleId)
  const line: CSSProperties = { fontSize: 'var(--k-text-label)', fontFamily: 'var(--k-font-mono)', color: 'var(--k-muted)', lineHeight: 1.7 }
  if (isLoading) return <p style={{ ...line, margin: 0, paddingLeft: 46 }}>Loading history…</p>
  if (execs.length === 0) return <p style={{ ...line, margin: 0, paddingLeft: 46 }}>No runs yet.</p>
  return (
    <div style={{ paddingLeft: 46, display: 'flex', flexDirection: 'column' }}>
      {execs.map(e => (
        <div key={e.id} style={{ ...line, color: e.status === 'ok' ? 'var(--k-muted)' : 'var(--k-health-err)', wordBreak: 'break-all' }}>
          [{e.started_at.replace('T', ' ').slice(0, 19)}] {e.status}{e.error ? ` — ${e.error}` : ''}
        </div>
      ))}
    </div>
  )
}
