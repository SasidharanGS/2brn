import type { CSSProperties, ReactNode } from 'react'
import { useTheme, type Skin } from '../../theme/ThemeContext'
import {
  useSettingsForm, CHAT_PROVIDER_OPTIONS, EMBED_PROVIDER_OPTIONS,
} from '../../hooks/useSettingsForm'
import PageHeader from './PageHeader'
import { Card, Field, GhostButton, Switch, lineInput } from './primitives'

const lineSelect: CSSProperties = { ...lineInput, cursor: 'pointer', appearance: 'none', borderRadius: 0 }

const quietBtn: CSSProperties = {
  background: 'none', border: 'none', padding: '2px 4px', cursor: 'pointer',
  fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-wide)',
  fontWeight: 300, fontFamily: 'var(--font-sans)',
}

/** Label + hint on the left, a switch (or other control) on the right. */
function SettingRow({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 'var(--space-md)', alignItems: 'start' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <div style={{ fontSize: 'var(--text-base)', color: 'var(--fg)', fontWeight: 300 }}>{label}</div>
        {hint && (
          <div style={{
            fontSize: 'var(--text-2xs)', color: 'var(--muted)', fontWeight: 300,
            letterSpacing: 'var(--tracking-wide)', lineHeight: 'var(--leading-snug)',
          }}>
            {hint}
          </div>
        )}
      </div>
      {children}
    </div>
  )
}

export default function Settings() {
  const { skin, setSkin } = useTheme()
  const {
    settings, exclusions,
    form, setField, tuning, setTuningField,
    saveMessage, flash,
    daemonOwned, restartState, handleRestartDaemon,
    includeSparse, setIncludeSparse, backfillResult, resyncResult,
    newApp, setNewApp,
    encPwd, setEncPwd, encPwdConfirm, setEncPwdConfirm,
    encOldPwd, setEncOldPwd, encNewPwd, setEncNewPwd,
    encNewPwdConfirm, setEncNewPwdConfirm, encDisablePwd, setEncDisablePwd,
    encMode, setEncMode,
    saveProviders, togglePause, saveTuning,
    runBackfill, runResync, addExclusion, removeExclusion,
    enableEncryption, changeEncryption, disableEncryption,
  } = useSettingsForm()

  if (!settings) {
    return (
      <div style={{ padding: 'var(--space-lg)' }}>
        <div style={{ fontSize: 'var(--text-base)', color: 'var(--muted)', fontWeight: 300 }}>loading…</div>
      </div>
    )
  }

  const cardGap: CSSProperties = { marginBottom: 'var(--space-sm)' }

  return (
    <div style={{ padding: 'var(--space-lg)' }}>
      <div style={{ maxWidth: 'var(--measure)' }}>
        <PageHeader title="settings" subtitle="~/.2brn/config.json" />

        {saveMessage && (
          <div style={{
            border: '1px solid var(--rule)', padding: 'var(--space-sm) var(--space-md)',
            marginBottom: 'var(--space-sm)', fontSize: 'var(--text-base)',
            color: 'var(--fg)', fontWeight: 300,
          }}>
            {saveMessage.toLowerCase()}
          </div>
        )}

        {/* Appearance */}
        <Card label="appearance" style={cardGap}>
          <Field label="theme" hint="stored locally, applies instantly.">
            <select value={skin} onChange={e => setSkin(e.target.value as Skin)} style={lineSelect}>
              <option value="modern">modern — the original look</option>
              <option value="minimal">minimal — monochrome, text-first</option>
            </select>
          </Field>
        </Card>

        {/* Capture */}
        <Card label="capture" style={cardGap}>
          <SettingRow
            label={settings.paused ? 'capture paused' : 'capture active'}
            hint="toggle background screen capture."
          >
            <Switch
              on={!settings.paused}
              onToggle={() => togglePause.mutate(!settings.paused)}
              disabled={togglePause.isPending}
            />
          </SettingRow>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-md)' }}>
            <Field label="heartbeat interval" hint="seconds between forced captures.">
              <input id="cap-interval" type="number" min={1} step={1} style={lineInput}
                value={tuning.interval} onChange={e => setTuningField('interval', e.target.value)} />
            </Field>
            <Field label="change cooldown" hint="min seconds between change captures.">
              <input id="cap-cooldown" type="number" min={0} step={0.5} style={lineInput}
                value={tuning.cooldown} onChange={e => setTuningField('cooldown', e.target.value)} />
            </Field>
            <Field label="max idle tick" hint="sampling backoff ceiling, seconds.">
              <input id="cap-idle-tick" type="number" min={1} step={1} style={lineInput}
                value={tuning.idleTick} onChange={e => setTuningField('idleTick', e.target.value)} />
            </Field>
            <Field label="similarity threshold" hint="phash duplicate cutoff (0.5–1.0).">
              <input id="cap-threshold" type="number" min={0.51} max={1} step={0.01} style={lineInput}
                value={tuning.threshold} onChange={e => setTuningField('threshold', e.target.value)} />
            </Field>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{
              fontSize: 'var(--text-2xs)', color: 'var(--muted)', fontWeight: 300,
              letterSpacing: 'var(--tracking-wide)',
            }}>
              applied on the next daemon restart
            </span>
            <GhostButton onClick={() => saveTuning.mutate()} disabled={saveTuning.isPending}>
              {saveTuning.isPending ? 'saving…' : 'save capture settings'}
            </GhostButton>
          </div>
        </Card>

        {/* Chat provider */}
        <Card label="chat provider" style={cardGap}>
          <Field label="provider">
            <select id="chat-type" value={form.chatType} onChange={e => setField('chatType', e.target.value)} style={lineSelect}>
              {CHAT_PROVIDER_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label.toLowerCase()}</option>
              ))}
            </select>
          </Field>
          <Field label="base url">
            <input id="chat-url" value={form.chatUrl} onChange={e => setField('chatUrl', e.target.value)}
              placeholder="e.g. http://localhost:11434/v1 (ollama)" style={lineInput} />
          </Field>
          <Field label="model">
            <input id="chat-model" value={form.chatModel} onChange={e => setField('chatModel', e.target.value)}
              placeholder="e.g. gpt-4o / claude-sonnet-4-6" style={lineInput} />
          </Field>
          <Field label="api key" hint={settings.has_chat_key ? 'stored in the os keychain — never written to disk.' : 'not set.'}>
            <input type="password" value={form.chatKey} onChange={e => setField('chatKey', e.target.value)}
              placeholder="enter new key to update…" style={lineInput} />
          </Field>
        </Card>

        {/* Embed provider */}
        <Card label="embed provider" style={cardGap}>
          <Field label="format" hint="openai covers most providers; custom is for gateways with a non-standard response shape.">
            <select id="embed-type" value={form.embedType} onChange={e => setField('embedType', e.target.value)} style={lineSelect}>
              {EMBED_PROVIDER_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label.toLowerCase()}</option>
              ))}
            </select>
          </Field>
          <Field label="base url">
            <input id="embed-url" value={form.embedUrl} onChange={e => setField('embedUrl', e.target.value)}
              placeholder="e.g. http://localhost:11434 (ollama)" style={lineInput} />
          </Field>
          <Field label="model">
            <input id="embed-model" value={form.embedModel} onChange={e => setField('embedModel', e.target.value)}
              placeholder="e.g. text-embedding-3-large" style={lineInput} />
          </Field>
          <Field label="api key" hint={settings.has_embed_key ? 'stored in the os keychain.' : 'not set.'}>
            <input type="password" value={form.embedKey} onChange={e => setField('embedKey', e.target.value)}
              placeholder="enter new key to update…" style={lineInput} />
          </Field>
          <div>
            <GhostButton accent onClick={() => saveProviders.mutate()} disabled={saveProviders.isPending}>
              {saveProviders.isPending ? 'saving…' : 'save provider settings'}
            </GhostButton>
          </div>
        </Card>

        {/* Excluded apps */}
        <Card label="excluded apps" style={cardGap}>
          <p style={{
            margin: 0, fontSize: 'var(--text-base)', color: 'var(--muted)', fontWeight: 300,
            lineHeight: 'var(--leading-normal)',
          }}>
            apps listed here will never be captured — add password managers, banking apps, etc.
          </p>
          <div style={{ display: 'flex', gap: 'var(--space-sm)', alignItems: 'flex-end' }}>
            <input
              value={newApp}
              onChange={e => setNewApp(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && newApp.trim() && addExclusion.mutate()}
              placeholder="app name (e.g. 1password)"
              style={lineInput}
            />
            <GhostButton onClick={() => newApp.trim() && addExclusion.mutate()} disabled={addExclusion.isPending || !newApp.trim()}>
              add
            </GhostButton>
          </div>
          {exclusions.length === 0 ? (
            <p style={{ margin: 0, fontSize: 'var(--text-2xs)', color: 'var(--muted)', fontWeight: 300, letterSpacing: 'var(--tracking-wide)' }}>
              no excluded apps.
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {exclusions.map(ex => (
                <div key={ex.app_name} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  borderTop: '1px solid var(--rule)', padding: 'var(--space-xs) 0',
                }}>
                  <span style={{ fontSize: 'var(--text-base)', color: 'var(--fg)', fontWeight: 300 }}>{ex.app_name}</span>
                  <button type="button" onClick={() => removeExclusion.mutate(ex.app_name)} className="m-quiet" style={quietBtn}>
                    remove
                  </button>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Screenshot encryption */}
        <Card label="screenshot encryption" style={cardGap}>
          <p style={{
            margin: 0, fontSize: 'var(--text-base)', color: 'var(--muted)', fontWeight: 300,
            lineHeight: 'var(--leading-normal)',
          }}>
            encrypt every screenshot at rest with aes-256-gcm. the password is stored in your os
            keychain; if you forget it, all encrypted screenshots are unrecoverable.
          </p>

          {!settings.screenshot_encryption_enabled ? (
            <>
              <p style={{ margin: 0, fontSize: 'var(--text-2xs)', color: 'var(--muted)', fontWeight: 300, letterSpacing: 'var(--tracking-wide)' }}>
                status: disabled — screenshots are stored as plain jpegs.
              </p>
              <Field label="password" hint="min 8 characters.">
                <input type="password" value={encPwd} onChange={e => setEncPwd(e.target.value)}
                  placeholder="choose a password…" autoComplete="new-password" style={lineInput} />
              </Field>
              <Field label="confirm password">
                <input type="password" value={encPwdConfirm} onChange={e => setEncPwdConfirm(e.target.value)}
                  placeholder="re-enter password…" autoComplete="new-password" style={lineInput} />
              </Field>
              <div>
                <GhostButton
                  accent
                  onClick={() => {
                    if (encPwd.length < 8) { flash('Password must be at least 8 characters'); return }
                    if (encPwd !== encPwdConfirm) { flash('Passwords do not match'); return }
                    enableEncryption.mutate()
                  }}
                  disabled={enableEncryption.isPending || !encPwd || !encPwdConfirm}
                >
                  {enableEncryption.isPending ? 'enabling…' : 'enable encryption'}
                </GhostButton>
              </div>
            </>
          ) : encMode === 'idle' ? (
            <>
              <p style={{ margin: 0, fontSize: 'var(--text-2xs)', color: 'var(--fg)', fontWeight: 400, letterSpacing: 'var(--tracking-wide)' }}>
                status: enabled — new screenshots are encrypted at capture time.
              </p>
              <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
                <GhostButton onClick={() => setEncMode('change')}>change password</GhostButton>
                <GhostButton accent onClick={() => setEncMode('disable')}>disable encryption</GhostButton>
              </div>
            </>
          ) : encMode === 'change' ? (
            <>
              <Field label="current password">
                <input type="password" value={encOldPwd} onChange={e => setEncOldPwd(e.target.value)}
                  autoComplete="current-password" style={lineInput} />
              </Field>
              <Field label="new password" hint="min 8 characters.">
                <input type="password" value={encNewPwd} onChange={e => setEncNewPwd(e.target.value)}
                  autoComplete="new-password" style={lineInput} />
              </Field>
              <Field label="confirm new password">
                <input type="password" value={encNewPwdConfirm} onChange={e => setEncNewPwdConfirm(e.target.value)}
                  autoComplete="new-password" style={lineInput} />
              </Field>
              <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
                <GhostButton
                  accent
                  onClick={() => {
                    if (encNewPwd.length < 8) { flash('Password must be at least 8 characters'); return }
                    if (encNewPwd !== encNewPwdConfirm) { flash('Passwords do not match'); return }
                    changeEncryption.mutate()
                  }}
                  disabled={changeEncryption.isPending || !encOldPwd || !encNewPwd}
                >
                  {changeEncryption.isPending ? 'changing…' : 'change password'}
                </GhostButton>
                <GhostButton onClick={() => { setEncMode('idle'); setEncOldPwd(''); setEncNewPwd(''); setEncNewPwdConfirm('') }}>
                  cancel
                </GhostButton>
              </div>
            </>
          ) : (
            <>
              <p style={{ margin: 0, fontSize: 'var(--text-base)', color: 'var(--accent)', fontWeight: 300 }}>
                this will decrypt every existing screenshot and store them as plain jpegs.
              </p>
              <Field label="confirm with current password">
                <input type="password" value={encDisablePwd} onChange={e => setEncDisablePwd(e.target.value)}
                  autoComplete="current-password" style={lineInput} />
              </Field>
              <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
                <GhostButton accent onClick={() => disableEncryption.mutate()} disabled={disableEncryption.isPending || !encDisablePwd}>
                  {disableEncryption.isPending ? 'disabling…' : 'disable & decrypt all'}
                </GhostButton>
                <GhostButton onClick={() => { setEncMode('idle'); setEncDisablePwd('') }}>cancel</GhostButton>
              </div>
            </>
          )}
        </Card>

        {/* Storage */}
        <Card label="storage" style={cardGap}>
          <p style={{ margin: 0, fontSize: 'var(--text-base)', color: 'var(--muted)', fontWeight: 300, lineHeight: 'var(--leading-normal)' }}>
            auto-purge: screenshots older than{' '}
            <span style={{ color: 'var(--fg)', fontWeight: 400 }}>{settings.purge_months} months</span>
            {' '}are automatically deleted. data stored at{' '}
            <code style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85em', color: 'var(--fg)' }}>~/.2brn/</code>
          </p>
        </Card>

        {/* Maintenance */}
        <Card label="maintenance" style={cardGap}>
          <SettingRow
            label="re-classify missed captures"
            hint="re-runs ai inference for captures that were observed but never classified (provider outages, queue overflows). uses your llm provider."
          >
            <GhostButton
              onClick={() => {
                if (window.confirm('Re-run AI inference for unclassified captures? This uses your LLM provider.')) {
                  runBackfill.mutate()
                }
              }}
              disabled={runBackfill.isPending}
            >
              {runBackfill.isPending ? 'running…' : 'run'}
            </GhostButton>
          </SettingRow>
          <SettingRow
            label="include screens without readable text"
            hint="videos, images — ~1 llm call per window title."
          >
            <Switch on={includeSparse} onToggle={() => setIncludeSparse(!includeSparse)} />
          </SettingRow>
          {backfillResult && (
            <p style={{ margin: 0, fontSize: 'var(--text-2xs)', color: 'var(--muted)', fontWeight: 300, letterSpacing: 'var(--tracking-wide)', lineHeight: 'var(--leading-snug)' }}>
              {backfillResult.toLowerCase()}
            </p>
          )}

          <div style={{ borderTop: '1px solid var(--rule)', paddingTop: 'var(--space-md)' }}>
            <SettingRow
              label="re-sync chromadb"
              hint="re-embeds activities missing from the semantic search index (used by chat). runs in the background."
            >
              <GhostButton
                onClick={() => {
                  if (window.confirm('Re-embed activities missing from ChromaDB? This uses your embedding provider.')) {
                    runResync.mutate()
                  }
                }}
                disabled={runResync.isPending}
              >
                {runResync.isPending ? 'running…' : 'run'}
              </GhostButton>
            </SettingRow>
            {resyncResult && (
              <p style={{ margin: 'var(--space-xs) 0 0', fontSize: 'var(--text-2xs)', color: 'var(--muted)', fontWeight: 300, letterSpacing: 'var(--tracking-wide)', lineHeight: 'var(--leading-snug)' }}>
                {resyncResult.toLowerCase()}
              </p>
            )}
          </div>
        </Card>

        {/* Integrations */}
        <Card label="integrations" style={cardGap}>
          <SettingRow
            label="joplin sync"
            hint="embed your notes into the same semantic index as screen activity. reads the local joplin sqlite db every 60s — purely additive, no writes to joplin. to send things back, add the joplin mcp server in plugins."
          >
            <Switch on={form.joplinEnabled} onToggle={() => setField('joplinEnabled', !form.joplinEnabled)} />
          </SettingRow>
          {form.joplinEnabled && (
            <Field label="joplin database path" hint="leave blank for the default ~/.config/joplin-desktop/database.sqlite">
              <input
                type="text" value={form.joplinDbPath} onChange={e => setField('joplinDbPath', e.target.value)}
                placeholder="/Users/me/.config/joplin-desktop/database.sqlite" spellCheck={false}
                style={{ ...lineInput, fontFamily: 'var(--font-mono)' }}
              />
            </Field>
          )}
          <p style={{ margin: 0, fontSize: 'var(--text-2xs)', color: 'var(--muted)', fontWeight: 300, letterSpacing: 'var(--tracking-wide)' }}>
            saved with the provider settings above.
          </p>
        </Card>

        {/* Daemon */}
        <Card label="daemon">
          {daemonOwned === false ? (
            <p style={{ margin: 0, fontSize: 'var(--text-base)', color: 'var(--muted)', fontWeight: 300 }}>
              daemon was started externally — restart not available.
            </p>
          ) : (
            <SettingRow label="restart daemon" hint="stops and restarts the background process.">
              <GhostButton
                accent
                onClick={handleRestartDaemon}
                disabled={restartState === 'restarting' || daemonOwned === null}
              >
                {restartState === 'restarting' ? 'restarting…' : 'restart daemon'}
              </GhostButton>
            </SettingRow>
          )}
        </Card>
      </div>
    </div>
  )
}
