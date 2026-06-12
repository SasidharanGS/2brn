import { useState, type CSSProperties } from 'react'
import type { Plugin, PluginRule } from '../../api/types'
import {
  usePluginsList, useNewPluginForm, usePluginDetail,
  useRuleActions, useRuleEditor, useRuleExecutions,
} from '../../hooks/usePlugins'
import Icon from './Icon'
import { Label, Pill, GhostButton, EmptyState, Switch, Field, lineInput } from './primitives'

const quietBtn: CSSProperties = {
  background: 'none', border: 'none', padding: '2px 4px', cursor: 'pointer',
  fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-wide)',
  fontWeight: 300, fontFamily: 'var(--font-sans)',
}

const boxArea: CSSProperties = {
  background: 'none', border: 'none', borderBottom: '1px solid var(--rule)',
  padding: '6px 0', color: 'var(--fg)', fontSize: 'var(--text-base)',
  fontWeight: 300, lineHeight: 'var(--leading-normal)', fontFamily: 'var(--font-mono)',
  outline: 'none', width: '100%', resize: 'vertical',
}

export default function Plugins() {
  const {
    plugins, isLoading,
    selectedId, setSelectedId, selected,
    showNewPlugin, setShowNewPlugin,
    invalidatePlugins,
  } = usePluginsList()

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '240px 1fr', gap: 0, height: '100%' }}>
      {/* ── Left pane: plugin list ── */}
      <div style={{
        borderRight: '1px solid var(--rule)', padding: 'var(--space-lg) var(--space-md)',
        overflowY: 'auto', minHeight: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 'var(--space-sm)' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
            <h1 style={{
              margin: 0, fontSize: 'var(--text-xl)', fontWeight: 400,
              letterSpacing: 'var(--tracking-tight)', color: 'var(--fg)',
            }}>
              plugins
            </h1>
            <span style={{
              fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-wide)',
              color: 'var(--muted)', fontWeight: 300,
            }}>
              {plugins.length === 0 ? 'no plugins' : `${plugins.length} configured`}
            </span>
          </div>
          <GhostButton accent onClick={() => setShowNewPlugin(true)}>
            <Icon name="plus" size={13} />add
          </GhostButton>
        </div>

        <div style={{ marginTop: 'var(--space-md)', display: 'flex', flexDirection: 'column', gap: 2 }}>
          {isLoading && (
            <span style={{ fontSize: 'var(--text-base)', color: 'var(--muted)', fontWeight: 300 }}>loading…</span>
          )}
          {plugins.map(p => {
            const active = p.id === selectedId
            return (
              <button
                key={p.id} type="button" onClick={() => setSelectedId(p.id)}
                className={`m-nav-link${active ? ' active' : ''}`}
                style={{
                  display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 2,
                  background: 'none', border: 'none', textAlign: 'left',
                  padding: '6px 0', cursor: 'pointer', width: '100%',
                  fontFamily: 'var(--font-sans)',
                  opacity: p.enabled ? 1 : 0.55,
                }}
              >
                <span style={{
                  display: 'inline-flex', alignItems: 'center', gap: 7,
                  fontSize: 'var(--text-sm)', letterSpacing: 'var(--tracking-wide)',
                }}>
                  <span style={{
                    width: 6, height: 6, borderRadius: '50%', flex: '0 0 auto',
                    background: p.last_health_ok === false ? 'var(--accent)' : p.last_health_ok ? 'var(--fg)' : 'var(--rule)',
                  }} title={p.last_health_error ?? (p.last_health_ok ? 'healthy' : 'unknown')} />
                  {p.name}
                </span>
                <span style={{
                  fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)', color: 'var(--muted)',
                  fontWeight: 300, overflow: 'hidden', textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap', maxWidth: '100%',
                }}>
                  {p.command}{p.args.length > 0 && ' …'}
                </span>
              </button>
            )
          })}
          {!isLoading && plugins.length === 0 && !showNewPlugin && (
            <p style={{
              marginTop: 'var(--space-md)', fontSize: 'var(--text-base)', color: 'var(--muted)',
              fontWeight: 300, lineHeight: 'var(--leading-normal)',
            }}>
              no plugins yet. add an mcp server to give 2brn new abilities.
            </p>
          )}
        </div>
      </div>

      {/* ── Right pane ── */}
      <div style={{ minWidth: 0, minHeight: 0, overflowY: 'auto' }}>
        {showNewPlugin ? (
          <NewPluginForm
            onCancel={() => setShowNewPlugin(false)}
            onCreated={p => {
              setShowNewPlugin(false)
              setSelectedId(p.id)
              invalidatePlugins()
            }}
          />
        ) : selected ? (
          <PluginDetail plugin={selected} onDeleted={() => setSelectedId(null)} />
        ) : (
          <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'var(--space-lg)' }}>
            <EmptyState icon={<Icon name="plugins" size={34} strokeWidth={1.2} />} title="plugins extend 2brn with mcp servers">
              add a model context protocol server (joplin, notion, slack, anything) and write
              natural-language rules that fire when events happen — like "when my journal is
              generated, save it to joplin".
            </EmptyState>
          </div>
        )}
      </div>
    </div>
  )
}

function NewPluginForm({ onCancel, onCreated }: { onCancel: () => void; onCreated: (p: Plugin) => void }) {
  const {
    name, setName, command, setCommand,
    argsText, setArgsText, envText, setEnvText,
    error, saving, handleSave,
  } = useNewPluginForm(onCreated)

  return (
    <div style={{ padding: 'var(--space-lg)' }}>
      <div style={{ maxWidth: 'var(--measure)', display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
        <div>
          <h1 style={{
            margin: 0, fontSize: 'var(--text-xl)', fontWeight: 400,
            letterSpacing: 'var(--tracking-tight)', color: 'var(--fg)',
          }}>
            add a plugin
          </h1>
          <p style={{
            margin: 'var(--space-xs) 0 0', fontSize: 'var(--text-base)', color: 'var(--muted)',
            fontWeight: 300, lineHeight: 'var(--leading-normal)',
          }}>
            plugins are mcp servers — local commands 2brn launches over stdio. once a plugin is
            added, you can write natural-language rules that call its tools.
          </p>
        </div>

        <Field label="name" hint="internal identifier. lowercase, no spaces. used as keychain namespace.">
          <input autoFocus value={name} onChange={e => setName(e.target.value)} placeholder="joplin" style={lineInput} />
        </Field>
        <Field label="command" hint="executable to launch (e.g. node, python, /usr/local/bin/foo).">
          <input
            value={command} onChange={e => setCommand(e.target.value)} placeholder="node"
            style={{ ...lineInput, fontFamily: 'var(--font-mono)' }}
          />
        </Field>
        <Field label="arguments (one per line)">
          <textarea
            value={argsText} onChange={e => setArgsText(e.target.value)} rows={3}
            placeholder="/Users/me/tools/joplin-mcp-server/dist/index.js"
            style={boxArea}
          />
        </Field>
        <Field label="environment variables (KEY=value, one per line)" hint="values are stored in the os keychain. only the key names persist in 2brn's database.">
          <textarea
            value={envText} onChange={e => setEnvText(e.target.value)} rows={3}
            placeholder={'JOPLIN_TOKEN=...\nJOPLIN_PORT=41184'}
            style={boxArea}
          />
        </Field>

        {error && (
          <div style={{ fontSize: 'var(--text-base)', color: 'var(--accent)', fontWeight: 300 }}>{error}</div>
        )}

        <div style={{ display: 'flex', gap: 'var(--space-sm)', justifyContent: 'flex-end' }}>
          <GhostButton onClick={onCancel}>cancel</GhostButton>
          <GhostButton accent onClick={handleSave} disabled={saving}>
            {saving ? 'saving…' : 'add plugin'}
          </GhostButton>
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
    <div style={{ padding: 'var(--space-lg)', display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
      {/* Header */}
      <div style={{ borderBottom: '1px solid var(--rule)', paddingBottom: 'var(--space-md)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--space-sm)' }}>
          <div style={{ minWidth: 0, display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
            <h1 style={{
              margin: 0, fontSize: 'var(--text-xl)', fontWeight: 400,
              letterSpacing: 'var(--tracking-tight)', color: 'var(--fg)',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {plugin.name}
            </h1>
            {plugin.last_health_ok === true && <Pill>healthy</Pill>}
            {plugin.last_health_ok === false && (
              <span
                title={plugin.last_health_error ?? 'unknown error'}
                style={{ fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-wide)', color: 'var(--accent)', fontWeight: 400 }}
              >
                error
              </span>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', flex: '0 0 auto' }}>
            <Switch on={plugin.enabled} onToggle={() => togglePluginMut.mutate()} />
            <button type="button" onClick={() => setShowAdvanced(v => !v)} className="m-quiet" style={quietBtn}>
              {showAdvanced ? 'hide' : 'config'}
            </button>
          </div>
        </div>
        <p style={{
          margin: 'var(--space-xs) 0 0', fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)',
          color: 'var(--muted)', fontWeight: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {plugin.command} {plugin.args.join(' ')}
        </p>
        {plugin.last_health_error && (
          <p style={{ margin: 'var(--space-xs) 0 0', fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)', color: 'var(--accent)' }}>
            {plugin.last_health_error}
          </p>
        )}
      </div>

      {/* Advanced */}
      {showAdvanced && (
        <div style={{
          border: '1px solid var(--rule)', padding: 'var(--space-md)',
          display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)',
        }}>
          <div>
            <Label>environment keys</Label>
            <p style={{ margin: '4px 0 0', fontSize: 'var(--text-base)', fontFamily: 'var(--font-mono)', color: 'var(--muted)', fontWeight: 300 }}>
              {plugin.env_keys.length === 0 ? '(none)' : plugin.env_keys.join(', ')}
            </p>
          </div>
          <div>
            <Label>available tools</Label>
            <p style={{ margin: '4px 0 0', fontSize: 'var(--text-base)', fontFamily: 'var(--font-mono)', color: 'var(--muted)', fontWeight: 300 }}>
              {tools.length === 0 ? '(loading or unavailable)' : tools.map(t => t.name).join(', ')}
            </p>
          </div>
          {confirmDelete ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
              <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--accent)', letterSpacing: 'var(--tracking-wide)' }}>
                delete this plugin and all its rules?
              </span>
              <button type="button" onClick={() => deletePluginMut.mutate()} style={{ ...quietBtn, color: 'var(--accent)' }}>
                yes, delete
              </button>
              <button type="button" onClick={() => setConfirmDelete(false)} className="m-quiet" style={quietBtn}>
                cancel
              </button>
            </div>
          ) : (
            <button
              type="button" onClick={() => setConfirmDelete(true)}
              style={{ ...quietBtn, color: 'var(--accent)', alignSelf: 'flex-start', padding: 0 }}
            >
              delete plugin
            </button>
          )}
        </div>
      )}

      {/* Rules */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-sm)' }}>
          <div>
            <Label>rules</Label>
            <p style={{ margin: '4px 0 0', fontSize: 'var(--text-2xs)', color: 'var(--muted)', fontWeight: 300, letterSpacing: 'var(--tracking-wide)' }}>
              plain-english instructions that turn into mcp tool calls when events fire.
            </p>
          </div>
          <GhostButton accent onClick={() => { setShowNewRule(true); setEditingRuleId(null) }}>
            <Icon name="plus" size={13} />new rule
          </GhostButton>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
          {showNewRule && (
            <RuleEditor
              mode="create" pluginId={plugin.id}
              onCancel={() => setShowNewRule(false)}
              onSaved={() => { setShowNewRule(false); invalidateRules() }}
            />
          )}

          {rules.map(rule =>
            editingRuleId === rule.id ? (
              <RuleEditor
                key={rule.id} mode="edit" pluginId={plugin.id} rule={rule}
                onCancel={() => setEditingRuleId(null)}
                onSaved={() => { setEditingRuleId(null); invalidateRules() }}
              />
            ) : (
              <RuleCard key={rule.id} rule={rule} onEdit={() => setEditingRuleId(rule.id)} />
            )
          )}

          {!showNewRule && rules.length === 0 && (
            <EmptyState dashed title="no rules yet.">
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.7rem' }}>
                example: "when my journal is generated, append it to the journal note in joplin."
              </span>
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
    <div style={{
      border: '1px solid var(--rule)', padding: 'var(--space-md)',
      display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)',
      opacity: rule.enabled ? 1 : 0.55,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
        <Switch on={rule.enabled} onToggle={() => toggleMut.mutate()} />
        <span style={{
          flex: 1, fontSize: 'var(--text-md)', color: 'var(--fg)', fontWeight: 400,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0,
        }}>
          {rule.title}
        </span>
        {rule.parse_status === 'ok' && <Pill>{rule.trigger || 'ready'}</Pill>}
        {rule.parse_status === 'error' && (
          <span
            title={rule.parse_error ?? undefined}
            style={{ fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-wide)', color: 'var(--accent)', fontWeight: 400, whiteSpace: 'nowrap' }}
          >
            parse error
          </span>
        )}
        {rule.parse_status !== 'ok' && rule.parse_status !== 'error' && (
          <span style={{ fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-wide)', color: 'var(--muted)', fontWeight: 300 }}>
            parsing…
          </span>
        )}
        {rule.tool_name && (
          <span style={{ fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)', color: 'var(--muted)', whiteSpace: 'nowrap' }}>
            → {rule.tool_name}
          </span>
        )}
      </div>

      <p style={{
        margin: 0, paddingLeft: 46, fontSize: 'var(--text-base)', color: 'var(--muted)',
        fontWeight: 300, lineHeight: 'var(--leading-normal)', whiteSpace: 'pre-wrap',
      }}>
        {rule.rule_text}
      </p>

      {rule.parse_error && (
        <p style={{ margin: 0, paddingLeft: 46, fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)', color: 'var(--accent)' }}>
          {rule.parse_error}
        </p>
      )}

      <div style={{ display: 'flex', gap: 'var(--space-sm)', justifyContent: 'flex-end', alignItems: 'center' }}>
        <button type="button" onClick={() => setShowExec(v => !v)} className="m-quiet" style={quietBtn}>
          {showExec ? 'hide history' : 'history'}
        </button>
        <button
          type="button" onClick={() => runMut.mutate()}
          disabled={rule.parse_status !== 'ok' || runMut.isPending}
          style={{ ...quietBtn, color: 'var(--accent)', opacity: rule.parse_status !== 'ok' || runMut.isPending ? 0.5 : 1 }}
        >
          {runMut.isPending ? 'running…' : 'run now'}
        </button>
        <button type="button" onClick={() => reparseMut.mutate()} disabled={reparseMut.isPending} className="m-quiet" style={quietBtn}>
          re-parse
        </button>
        <button type="button" onClick={onEdit} className="m-quiet" style={quietBtn}>edit</button>
        {confirmDelete ? (
          <>
            <button type="button" onClick={() => { setConfirmDelete(false); deleteMut.mutate() }} style={{ ...quietBtn, color: 'var(--accent)' }}>
              confirm
            </button>
            <button type="button" onClick={() => setConfirmDelete(false)} className="m-quiet" style={quietBtn}>
              cancel
            </button>
          </>
        ) : (
          <button type="button" onClick={() => setConfirmDelete(true)} className="m-quiet" style={quietBtn}>
            delete
          </button>
        )}
      </div>

      {showExec && <ExecutionHistory ruleId={rule.id} />}
    </div>
  )
}

function RuleEditor({ mode, pluginId, rule, onCancel, onSaved }: {
  mode: 'create' | 'edit'
  pluginId: number
  rule?: PluginRule
  onCancel: () => void
  onSaved: () => void
}) {
  const { title, setTitle, text, setText, error, saving, handleSave } =
    useRuleEditor(mode, pluginId, rule, onSaved)

  return (
    <div style={{
      border: '1px solid var(--muted)', padding: 'var(--space-md)',
      display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)',
    }}>
      <input
        autoFocus value={title} onChange={e => setTitle(e.target.value)}
        placeholder="rule title (e.g. mirror journal to joplin)"
        style={lineInput}
      />
      <textarea
        value={text} onChange={e => setText(e.target.value)} rows={4}
        placeholder={'when my journal is generated, create a joplin note in the "journal" notebook titled with today\'s date and the journal content as the body.'}
        style={{ ...boxArea, fontFamily: 'var(--font-sans)' }}
      />
      <p style={{ margin: 0, fontSize: '0.66rem', fontFamily: 'var(--font-mono)', color: 'var(--muted)', lineHeight: 'var(--leading-loose)' }}>
        triggers: journal_generated · blog_generated · capture_inferred · daily_at_HH:MM · every_Xs · manual.
        placeholders: {'{date}'} {'{journal_content}'} {'{blog_content}'} {'{summary}'} {'{task_category}'} {'{app_name}'}
      </p>

      {error && (
        <div style={{ fontSize: 'var(--text-base)', color: 'var(--accent)', fontWeight: 300 }}>{error}</div>
      )}

      <div style={{ display: 'flex', gap: 'var(--space-sm)', justifyContent: 'flex-end' }}>
        <GhostButton onClick={onCancel}>cancel</GhostButton>
        <GhostButton accent onClick={handleSave} disabled={saving}>
          {saving ? 'parsing…' : mode === 'create' ? 'save rule' : 'save'}
        </GhostButton>
      </div>
    </div>
  )
}

function ExecutionHistory({ ruleId }: { ruleId: number }) {
  const { execs, isLoading } = useRuleExecutions(ruleId)

  const line: CSSProperties = {
    fontSize: '0.66rem', fontFamily: 'var(--font-mono)', color: 'var(--muted)',
    lineHeight: 'var(--leading-loose)',
  }

  if (isLoading) return <p style={{ ...line, margin: 0, paddingLeft: 46 }}>loading history…</p>
  if (execs.length === 0) return <p style={{ ...line, margin: 0, paddingLeft: 46 }}>no runs yet.</p>

  return (
    <div style={{ paddingLeft: 46, display: 'flex', flexDirection: 'column' }}>
      {execs.map(e => (
        <div key={e.id} style={{ ...line, color: e.status === 'ok' ? 'var(--muted)' : 'var(--accent)', wordBreak: 'break-all' }}>
          [{e.started_at.replace('T', ' ').slice(0, 19)}] {e.status}{e.error ? ` — ${e.error}` : ''}
        </div>
      ))}
    </div>
  )
}
