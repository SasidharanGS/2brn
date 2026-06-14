import { useTheme, type Skin } from '../theme/ThemeContext'
import { useSettingsForm, CHAT_PROVIDER_OPTIONS, EMBED_PROVIDER_OPTIONS } from '../hooks/useSettingsForm'
import { Page, PageHeader, Section, Field, SettingRow, Input, Select, Switch, Button, QuietButton } from '../ui-kit'

// Unified Settings — one component for both skins. All form state, mutations
// and password validation live in useSettingsForm; the view is token-driven.
export default function Settings() {
  const { skin, setSkin } = useTheme()
  const s = useSettingsForm()
  const { settings, exclusions, form, setField, tuning, setTuningField, saveMessage } = s

  if (!settings) {
    return <Page max={640}><div style={{ fontSize: 'var(--k-text-body)', color: 'var(--k-muted)' }}>Loading…</div></Page>
  }

  return (
    <Page max={640}>
      <PageHeader title="Settings" subtitle="~/.2brn/config.json" />

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--k-space-md)' }}>
        {saveMessage && <div className="k-ok-banner">{saveMessage}</div>}

        <Section title="Appearance">
          <Field label="Theme" hint="Stored locally, applies instantly.">
            <Select value={skin} onChange={e => setSkin(e.target.value as Skin)}
              options={[
                { value: 'modern', label: 'Modern — the original look' },
                { value: 'minimal', label: 'Minimal — monochrome, text-first' },
              ]} />
          </Field>
        </Section>

        <Section title="Capture">
          <SettingRow label={settings.paused ? 'Capture paused' : 'Capture active'} hint="Toggle background screen capture.">
            <Switch on={!settings.paused} onToggle={() => s.togglePause.mutate(!settings.paused)} disabled={s.togglePause.isPending} />
          </SettingRow>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--k-space-md)' }}>
            <Field label="Heartbeat interval" hint="Seconds between forced captures.">
              <Input id="cap-interval" type="number" min={1} step={1} value={tuning.interval} onChange={e => setTuningField('interval', e.target.value)} />
            </Field>
            <Field label="Change cooldown" hint="Min seconds between change captures.">
              <Input id="cap-cooldown" type="number" min={0} step={0.5} value={tuning.cooldown} onChange={e => setTuningField('cooldown', e.target.value)} />
            </Field>
            <Field label="Max idle tick" hint="Sampling backoff ceiling, seconds.">
              <Input id="cap-idle-tick" type="number" min={1} step={1} value={tuning.idleTick} onChange={e => setTuningField('idleTick', e.target.value)} />
            </Field>
            <Field label="Similarity threshold" hint="phash duplicate cutoff (0.5–1.0).">
              <Input id="cap-threshold" type="number" min={0.51} max={1} step={0.01} value={tuning.threshold} onChange={e => setTuningField('threshold', e.target.value)} />
            </Field>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--k-space-sm)' }}>
            <span className="k-field-hint" style={{ marginTop: 0 }}>Applied on the next daemon restart</span>
            <Button variant="primary" onClick={() => s.saveTuning.mutate()} disabled={s.saveTuning.isPending}>
              {s.saveTuning.isPending ? 'Saving…' : 'Save capture settings'}
            </Button>
          </div>
        </Section>

        <Section title="Chat Provider">
          <Field label="Provider">
            <Select id="chat-type" options={CHAT_PROVIDER_OPTIONS} value={form.chatType} onChange={e => setField('chatType', e.target.value)} />
          </Field>
          <Field label="Base URL">
            <Input id="chat-url" value={form.chatUrl} onChange={e => setField('chatUrl', e.target.value)} placeholder="e.g. http://localhost:11434/v1 (Ollama)" />
          </Field>
          <Field label="Model">
            <Input id="chat-model" value={form.chatModel} onChange={e => setField('chatModel', e.target.value)} placeholder="e.g. gpt-4o / claude-sonnet-4-6" />
          </Field>
          <Field label="API Key" hint={settings.has_chat_key ? 'Stored in the OS keychain — never written to disk.' : 'Not set.'}>
            <Input type="password" value={form.chatKey} onChange={e => setField('chatKey', e.target.value)} placeholder="Enter new key to update…" />
          </Field>
        </Section>

        <Section title="Embed Provider">
          <Field label="Format" hint="OpenAI covers most providers; custom is for gateways with a non-standard response shape.">
            <Select id="embed-type" options={EMBED_PROVIDER_OPTIONS} value={form.embedType} onChange={e => setField('embedType', e.target.value)} />
          </Field>
          <Field label="Base URL">
            <Input id="embed-url" value={form.embedUrl} onChange={e => setField('embedUrl', e.target.value)} placeholder="e.g. http://localhost:11434 (Ollama)" />
          </Field>
          <Field label="Model">
            <Input id="embed-model" value={form.embedModel} onChange={e => setField('embedModel', e.target.value)} placeholder="e.g. text-embedding-3-large" />
          </Field>
          <Field label="API Key" hint={settings.has_embed_key ? 'Stored in the OS keychain.' : 'Not set.'}>
            <Input type="password" value={form.embedKey} onChange={e => setField('embedKey', e.target.value)} placeholder="Enter new key to update…" />
          </Field>
          <div>
            <Button variant="primary" onClick={() => s.saveProviders.mutate()} disabled={s.saveProviders.isPending}>
              {s.saveProviders.isPending ? 'Saving…' : 'Save provider settings'}
            </Button>
          </div>
        </Section>

        <Section title="Excluded Apps">
          <p className="k-field-hint" style={{ marginTop: 0 }}>Apps listed here will never be captured — add password managers, banking apps, etc.</p>
          <div style={{ display: 'flex', gap: 'var(--k-space-sm)', alignItems: 'flex-end' }}>
            <Input value={s.newApp} onChange={e => s.setNewApp(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && s.newApp.trim() && s.addExclusion.mutate()} placeholder="App name (e.g. 1Password)" />
            <Button variant="primary" onClick={() => s.newApp.trim() && s.addExclusion.mutate()} disabled={s.addExclusion.isPending || !s.newApp.trim()}>Add</Button>
          </div>
          {exclusions.length === 0 ? (
            <p className="k-field-hint" style={{ marginTop: 0 }}>No excluded apps.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {exclusions.map(ex => (
                <div key={ex.app_name} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid var(--k-rule)', padding: 'var(--k-space-xs) 0' }}>
                  <span style={{ fontSize: 'var(--k-text-body)', color: 'var(--k-fg)' }}>{ex.app_name}</span>
                  <QuietButton danger onClick={() => s.removeExclusion.mutate(ex.app_name)}>Remove</QuietButton>
                </div>
              ))}
            </div>
          )}
        </Section>

        <Section title="Screenshot Encryption">
          <p className="k-field-hint" style={{ marginTop: 0 }}>
            Encrypt every screenshot at rest with AES-256-GCM. The password is stored in your OS keychain;
            if you forget it, all encrypted screenshots are unrecoverable.
          </p>
          {!settings.screenshot_encryption_enabled ? (
            <>
              <p className="k-field-hint" style={{ marginTop: 0 }}>Status: disabled — screenshots are stored as plain JPEGs.</p>
              <Field label="Password" hint="Min 8 characters.">
                <Input type="password" value={s.encPwd} onChange={e => s.setEncPwd(e.target.value)} placeholder="Choose a password…" autoComplete="new-password" />
              </Field>
              <Field label="Confirm Password">
                <Input type="password" value={s.encPwdConfirm} onChange={e => s.setEncPwdConfirm(e.target.value)} placeholder="Re-enter password…" autoComplete="new-password" />
              </Field>
              <div>
                <Button variant="primary" onClick={s.submitEnableEncryption} disabled={s.enableEncryption.isPending || !s.encPwd || !s.encPwdConfirm}>
                  {s.enableEncryption.isPending ? 'Enabling…' : 'Enable encryption'}
                </Button>
              </div>
            </>
          ) : s.encMode === 'idle' ? (
            <>
              <p className="k-field-hint" style={{ marginTop: 0, color: 'var(--k-fg)' }}>Status: enabled — new screenshots are encrypted at capture time.</p>
              <div style={{ display: 'flex', gap: 'var(--k-space-sm)' }}>
                <Button onClick={() => s.setEncMode('change')}>Change password</Button>
                <Button variant="danger" onClick={() => s.setEncMode('disable')}>Disable encryption</Button>
              </div>
            </>
          ) : s.encMode === 'change' ? (
            <>
              <Field label="Current Password"><Input type="password" value={s.encOldPwd} onChange={e => s.setEncOldPwd(e.target.value)} autoComplete="current-password" /></Field>
              <Field label="New Password" hint="Min 8 characters."><Input type="password" value={s.encNewPwd} onChange={e => s.setEncNewPwd(e.target.value)} autoComplete="new-password" /></Field>
              <Field label="Confirm New Password"><Input type="password" value={s.encNewPwdConfirm} onChange={e => s.setEncNewPwdConfirm(e.target.value)} autoComplete="new-password" /></Field>
              <div style={{ display: 'flex', gap: 'var(--k-space-sm)' }}>
                <Button variant="primary" onClick={s.submitChangeEncryption} disabled={s.changeEncryption.isPending || !s.encOldPwd || !s.encNewPwd}>
                  {s.changeEncryption.isPending ? 'Changing…' : 'Change password'}
                </Button>
                <Button onClick={() => { s.setEncMode('idle'); s.setEncOldPwd(''); s.setEncNewPwd(''); s.setEncNewPwdConfirm('') }}>Cancel</Button>
              </div>
            </>
          ) : (
            <>
              <p style={{ margin: 0, fontSize: 'var(--k-text-meta)', color: 'var(--k-danger)' }}>This will decrypt every existing screenshot and store them as plain JPEGs.</p>
              <Field label="Confirm with Current Password"><Input type="password" value={s.encDisablePwd} onChange={e => s.setEncDisablePwd(e.target.value)} autoComplete="current-password" /></Field>
              <div style={{ display: 'flex', gap: 'var(--k-space-sm)' }}>
                <Button variant="danger" onClick={() => s.disableEncryption.mutate()} disabled={s.disableEncryption.isPending || !s.encDisablePwd}>
                  {s.disableEncryption.isPending ? 'Disabling…' : 'Disable & decrypt all'}
                </Button>
                <Button onClick={() => { s.setEncMode('idle'); s.setEncDisablePwd('') }}>Cancel</Button>
              </div>
            </>
          )}
        </Section>

        <Section title="Storage">
          <p className="k-field-hint" style={{ marginTop: 0 }}>
            Auto-purge: screenshots older than <span style={{ color: 'var(--k-fg)' }}>{settings.purge_months} months</span> are automatically deleted.
            Data stored at <code style={{ fontFamily: 'var(--k-font-mono)', fontSize: '0.85em', color: 'var(--k-fg)' }}>~/.2brn/</code>
          </p>
        </Section>

        <Section title="Maintenance">
          <SettingRow label="Re-classify missed captures" hint="Re-runs AI inference for captures that were observed but never classified (provider outages, queue overflows). Uses your LLM provider.">
            <Button variant="primary" onClick={() => { if (window.confirm('Re-run AI inference for unclassified captures? This uses your LLM provider.')) s.runBackfill.mutate() }} disabled={s.runBackfill.isPending}>
              {s.runBackfill.isPending ? 'Running…' : 'Run'}
            </Button>
          </SettingRow>
          <SettingRow label="Include screens without readable text" hint="Videos, images — ~1 LLM call per window title.">
            <Switch on={s.includeSparse} onToggle={() => s.setIncludeSparse(!s.includeSparse)} />
          </SettingRow>
          {s.backfillResult && <p className="k-field-hint" style={{ marginTop: 0 }}>{s.backfillResult}</p>}
          <div style={{ borderTop: '1px solid var(--k-rule)', paddingTop: 'var(--k-space-md)' }}>
            <SettingRow label="Re-sync ChromaDB" hint="Re-embeds activities missing from the semantic search index (used by chat). Runs in the background.">
              <Button variant="primary" onClick={() => { if (window.confirm('Re-embed activities missing from ChromaDB? This uses your embedding provider.')) s.runResync.mutate() }} disabled={s.runResync.isPending}>
                {s.runResync.isPending ? 'Running…' : 'Run'}
              </Button>
            </SettingRow>
            {s.resyncResult && <p className="k-field-hint">{s.resyncResult}</p>}
          </div>
        </Section>

        <Section title="Integrations">
          <SettingRow label="Joplin sync" hint="Embed your notes into the same semantic index as screen activity. Reads the local Joplin SQLite DB every 60s — purely additive, no writes to Joplin. To send things back, add the Joplin MCP server in Plugins.">
            <Switch on={form.joplinEnabled} onToggle={() => setField('joplinEnabled', !form.joplinEnabled)} />
          </SettingRow>
          {form.joplinEnabled && (
            <Field label="Joplin database path" hint="Leave blank for the default ~/.config/joplin-desktop/database.sqlite">
              <Input type="text" value={form.joplinDbPath} onChange={e => setField('joplinDbPath', e.target.value)} placeholder="/Users/me/.config/joplin-desktop/database.sqlite" spellCheck={false} style={{ fontFamily: 'var(--k-font-mono)' }} />
            </Field>
          )}
          <p className="k-field-hint" style={{ marginTop: 0 }}>Saved with the provider settings above.</p>
        </Section>

        <Section title="Daemon">
          {s.daemonOwned === false ? (
            <p className="k-field-hint" style={{ marginTop: 0 }}>Daemon was started externally — restart not available.</p>
          ) : (
            <SettingRow label="Restart daemon" hint="Stops and restarts the background process.">
              <Button variant="primary" onClick={s.handleRestartDaemon} disabled={s.restartState === 'restarting' || s.daemonOwned === null}>
                {s.restartState === 'restarting' ? 'Restarting…' : 'Restart daemon'}
              </Button>
            </SettingRow>
          )}
        </Section>
      </div>
    </Page>
  )
}
