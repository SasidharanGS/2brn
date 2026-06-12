import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { queryKeys } from '../api/queryKeys'

// ── Primitive design components ──────────────────────────────────────────────

function Field({ label, sublabel, children }: { label: string; sublabel?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-[13px] font-medium mb-1.5" style={{ color: 'var(--text-muted)' }}>
        {label}
        {sublabel && <span className="ml-2 font-normal text-[12px] opacity-60">{sublabel}</span>}
      </label>
      {children}
    </div>
  )
}

function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className="w-full rounded-[9px] border px-3 py-2 text-[14px] outline-none transition-shadow focus:shadow-glow-sm"
      style={{
        background: 'var(--bg-input)',
        borderColor: 'var(--border-2)',
        color: 'var(--text)',
        ...props.style,
      }}
    />
  )
}

function Select(props: React.SelectHTMLAttributes<HTMLSelectElement> & { options: { value: string; label: string }[] }) {
  const { options, ...rest } = props
  return (
    <select
      {...rest}
      className="w-full rounded-[9px] border px-3 py-2 text-[14px] outline-none transition-shadow focus:shadow-glow-sm appearance-none"
      style={{
        background: 'var(--bg-input)',
        borderColor: 'var(--border-2)',
        color: 'var(--text)',
        backgroundImage: 'url("data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 width=%2710%27 height=%276%27 viewBox=%270 0 10 6%27%3E%3Cpath fill=%27%23888%27 d=%27M5 6L0 0h10z%27/%3E%3C/svg%3E")',
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'right 12px center',
        paddingRight: '32px',
        ...rest.style,
      }}
    >
      {options.map(o => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  )
}

// ── Provider catalogues ──────────────────────────────────────────────────────

const CHAT_PROVIDER_OPTIONS = [
  { value: 'openai_compatible', label: 'OpenAI-Compatible (LM Studio, local gateway, etc.)' },
  { value: 'openai',            label: 'OpenAI' },
  { value: 'anthropic',         label: 'Anthropic' },
  { value: 'azure',             label: 'Azure OpenAI' },
  { value: 'ollama',            label: 'Ollama (local)' },
  { value: 'groq',              label: 'Groq' },
  { value: 'together',          label: 'Together AI' },
  { value: 'cohere',            label: 'Cohere' },
]

const EMBED_PROVIDER_OPTIONS = [
  { value: 'custom', label: 'Custom (non-standard format, e.g. enterprise gateways)' },
  { value: 'openai', label: 'OpenAI-Compatible (OpenAI, Azure, Ollama, etc.)' },
]

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section
      className="rounded-[12px] border p-5 space-y-4"
      style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
    >
      <h2
        className="text-[12px] font-semibold tracking-[0.08em] uppercase"
        style={{ color: 'var(--text-dim)' }}
      >
        {title}
      </h2>
      {children}
    </section>
  )
}

// ── Settings component ────────────────────────────────────────────────────────

export default function Settings() {
  const qc = useQueryClient()
  type FormState = {
    chatType: string; chatUrl: string; chatModel: string; chatKey: string
    embedType: string; embedUrl: string; embedModel: string; embedKey: string
    joplinEnabled: boolean; joplinDbPath: string
  }
  const [form, setForm] = useState<FormState>({
    chatType: '', chatUrl: '', chatModel: '', chatKey: '',
    embedType: '', embedUrl: '', embedModel: '', embedKey: '',
    joplinEnabled: false, joplinDbPath: '',
  })
  const setField = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm(prev => ({ ...prev, [key]: value }))
  // Capture tuning fields are kept as strings while editing; parsed on save.
  type TuningState = { interval: string; cooldown: string; idleTick: string; threshold: string }
  const [tuning, setTuning] = useState<TuningState>({ interval: '', cooldown: '', idleTick: '', threshold: '' })
  const setTuningField = <K extends keyof TuningState>(key: K, value: string) =>
    setTuning(prev => ({ ...prev, [key]: value }))
  // Maintenance actions
  const [includeSparse, setIncludeSparse] = useState(false)
  const [backfillResult, setBackfillResult] = useState('')
  const [resyncResult, setResyncResult] = useState('')
  const [newApp, setNewApp]       = useState('')
  const [saveMessage, setSaveMessage] = useState('')
  const [daemonOwned, setDaemonOwned] = useState<boolean | null>(null)
  const [restartState, setRestartState] = useState<'idle' | 'restarting'>('idle')
  const restartIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Screenshot encryption form state
  const [encPwd, setEncPwd]         = useState('')
  const [encPwdConfirm, setEncPwdConfirm] = useState('')
  const [encOldPwd, setEncOldPwd]   = useState('')
  const [encNewPwd, setEncNewPwd]   = useState('')
  const [encNewPwdConfirm, setEncNewPwdConfirm] = useState('')
  const [encDisablePwd, setEncDisablePwd] = useState('')
  const [encMode, setEncMode]       = useState<'idle' | 'change' | 'disable'>('idle')

  const { data: settings }     = useQuery({ queryKey: queryKeys.settings(),   queryFn: api.getSettings })
  const { data: exclusions = [] } = useQuery({ queryKey: queryKeys.exclusions(), queryFn: api.getExclusions })

  useEffect(() => {
    window.electronAPI.isDaemonOwned().then(setDaemonOwned).catch(() => setDaemonOwned(false))
  }, [])

  const mountedRef = useRef(true)
  useEffect(() => {
    return () => {
      mountedRef.current = false
      if (restartIntervalRef.current) clearInterval(restartIntervalRef.current)
    }
  }, [])

  useEffect(() => {
    if (!settings) return
    const active = document.activeElement as HTMLElement | null
    const activeId = active?.id ?? ''
    setForm(prev => ({
      chatType:     activeId === 'chat-type'  ? prev.chatType  : settings.chat_provider.type,
      chatUrl:      activeId === 'chat-url'   ? prev.chatUrl   : settings.chat_provider.base_url,
      chatModel:    activeId === 'chat-model' ? prev.chatModel : settings.chat_provider.model,
      chatKey:      prev.chatKey,
      embedType:    activeId === 'embed-type'  ? prev.embedType  : settings.embed_provider.type,
      embedUrl:     activeId === 'embed-url'   ? prev.embedUrl   : settings.embed_provider.base_url,
      embedModel:   activeId === 'embed-model' ? prev.embedModel : settings.embed_provider.model,
      embedKey:     prev.embedKey,
      joplinEnabled: settings.joplin_enabled ?? false,
      joplinDbPath:  settings.joplin_db_path ?? '',
    }))
    setTuning(prev => ({
      interval:  activeId === 'cap-interval'  ? prev.interval  : String(settings.capture_interval_seconds),
      cooldown:  activeId === 'cap-cooldown'  ? prev.cooldown  : String(settings.change_cooldown_seconds),
      idleTick:  activeId === 'cap-idle-tick' ? prev.idleTick  : String(settings.max_idle_tick_seconds),
      threshold: activeId === 'cap-threshold' ? prev.threshold : String(settings.similarity_threshold),
    }))
  }, [settings])

  const flash = (msg: string) => { setSaveMessage(msg); setTimeout(() => setSaveMessage(''), 3000) }

  function handleRestartDaemon() {
    if (restartState === 'restarting') return
    setRestartState('restarting')
    window.electronAPI.restartDaemon()

    const deadline = Date.now() + 15_000
    restartIntervalRef.current = setInterval(async () => {
      try {
        await api.getStatus()
        if (!mountedRef.current) return
        clearInterval(restartIntervalRef.current!)
        restartIntervalRef.current = null
        setRestartState('idle')
        flash('Daemon restarted successfully')
      } catch {
        if (!mountedRef.current) return
        if (Date.now() >= deadline) {
          clearInterval(restartIntervalRef.current!)
          restartIntervalRef.current = null
          setRestartState('idle')
          flash('Daemon did not come back up')
        }
      }
    }, 2000)
  }

  const saveProviders = useMutation({
    mutationFn: () => api.updateSettings({
      chat_provider: {
        type: form.chatType, base_url: form.chatUrl, model: form.chatModel,
        ...(form.chatKey ? { api_key: form.chatKey } : {}),
      },
      embed_provider: {
        type: form.embedType, base_url: form.embedUrl, model: form.embedModel,
        ...(form.embedKey ? { api_key: form.embedKey } : {}),
      },
      joplin_enabled: form.joplinEnabled,
      joplin_db_path: form.joplinDbPath.trim(),
    }),
    onSuccess: () => {
      setField('chatKey', ''); setField('embedKey', '')
      flash('Settings saved')
      qc.invalidateQueries({ queryKey: queryKeys.settings() })
    },
    onError: () => flash('Failed to save'),
  })

  const togglePause = useMutation({
    mutationFn: (paused: boolean) => api.setPaused(paused),
    onSuccess:  () => qc.invalidateQueries({ queryKey: queryKeys.settings() }),
  })

  const saveTuning = useMutation({
    mutationFn: () => {
      const interval  = parseInt(tuning.interval, 10)
      const cooldown  = parseFloat(tuning.cooldown)
      const idleTick  = parseFloat(tuning.idleTick)
      const threshold = parseFloat(tuning.threshold)
      if ([interval, cooldown, idleTick, threshold].some(Number.isNaN)) {
        return Promise.reject(new Error('invalid number'))
      }
      return api.updateSettings({
        capture_interval_seconds: interval,
        change_cooldown_seconds: cooldown,
        max_idle_tick_seconds: idleTick,
        similarity_threshold: threshold,
      })
    },
    onSuccess: () => {
      flash('Capture settings saved — restart the daemon to apply')
      qc.invalidateQueries({ queryKey: queryKeys.settings() })
    },
    onError: () => flash('Failed to save capture settings (check the values)'),
  })

  const runBackfill = useMutation({
    mutationFn: () => api.backfillActivities(includeSparse),
    onSuccess: (r) => {
      const parts = [`${r.queued} captures queued for inference`]
      if (r.remaining > 0) parts.push(`${r.remaining} more matched — run again to continue`)
      if (r.sparse_cloned !== undefined) {
        parts.push(`${r.sparse_cloned} cloned from matching window titles`)
        if (r.sparse_queued) parts.push(`${r.sparse_queued} window titles queued`)
        if (r.sparse_deferred) parts.push(`${r.sparse_deferred} deferred — run again once inference lands`)
      }
      setBackfillResult(parts.join(' · '))
    },
    onError: () => setBackfillResult('Backfill failed — is the daemon running?'),
  })

  const runResync = useMutation({
    mutationFn: () => api.resyncChroma(),
    onSuccess: (r) => setResyncResult(r.message || 'Re-sync started in background'),
    onError: () => setResyncResult('Re-sync failed — is the daemon running?'),
  })

  const addExclusion = useMutation({
    mutationFn: () => api.addExclusion(newApp.trim()),
    onSuccess:  () => { setNewApp(''); qc.invalidateQueries({ queryKey: queryKeys.exclusions() }) },
    onError:    () => flash('Already excluded'),
  })

  const removeExclusion = useMutation({
    mutationFn: (name: string) => api.removeExclusion(name),
    onSuccess:  () => qc.invalidateQueries({ queryKey: queryKeys.exclusions() }),
  })

  // ── Screenshot encryption mutations ────────────────────────────────────
  const enableEncryption = useMutation({
    mutationFn: () => api.setScreenshotPassword(encPwd, true),
    onSuccess: (r) => {
      setEncPwd(''); setEncPwdConfirm('')
      flash(r.message || 'Encryption enabled. Encrypting existing screenshots in background…')
      qc.invalidateQueries({ queryKey: queryKeys.settings() })
    },
    onError: () => flash('Failed to enable encryption'),
  })

  const changeEncryption = useMutation({
    mutationFn: () => api.changeScreenshotPassword(encOldPwd, encNewPwd),
    onSuccess: (r) => {
      setEncOldPwd(''); setEncNewPwd(''); setEncNewPwdConfirm(''); setEncMode('idle')
      flash(r.message || 'Password changed. Re-encrypting in background…')
      qc.invalidateQueries({ queryKey: queryKeys.settings() })
    },
    onError: () => flash('Failed to change password (check old password)'),
  })

  const disableEncryption = useMutation({
    mutationFn: () => api.disableScreenshotPassword(encDisablePwd, true),
    onSuccess: (r) => {
      setEncDisablePwd(''); setEncMode('idle')
      flash(r.message || 'Encryption disabled. Screenshots decrypted.')
      qc.invalidateQueries({ queryKey: queryKeys.settings() })
    },
    onError: () => flash('Failed to disable (check password)'),
  })

  // Loading skeleton
  if (!settings) {
    return (
      <div className="page-enter p-7 max-w-[640px] mx-auto space-y-4">
        <div className="skeleton h-7 w-24 rounded-[8px]" />
        {[...Array(3)].map((_, i) => <div key={i} className="skeleton h-36 rounded-[12px]" />)}
      </div>
    )
  }

  return (
    <div className="page-enter p-7 max-w-[640px] mx-auto space-y-4">
      <h1 className="text-[19px] font-semibold tracking-tight mb-2" style={{ color: 'var(--text)' }}>
        Settings
      </h1>

      {saveMessage && (
        <div
          className="px-4 py-3 rounded-[9px] text-[13px] border"
          style={{ background: 'var(--green-bg)', color: 'var(--green)', borderColor: 'rgba(52,211,153,0.2)' }}
        >
          {saveMessage}
        </div>
      )}

      {/* Capture */}
      <Section title="Capture">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-[14px]" style={{ color: 'var(--text)' }}>
              {settings.paused ? 'Capture paused' : 'Capture active'}
            </div>
            <div className="text-[12px] mt-0.5" style={{ color: 'var(--text-dim)' }}>
              Toggle background screen capture
            </div>
          </div>
          <button
            onClick={() => togglePause.mutate(!settings?.paused)}
            disabled={togglePause.isPending}
            className="px-4 py-2 rounded-[9px] text-[13px] font-medium transition-all disabled:opacity-40"
            style={settings.paused
              ? { background: 'var(--green-bg)', color: 'var(--green)', border: '1px solid rgba(52,211,153,0.2)' }
              : { background: 'var(--red-bg)',   color: 'var(--red)',   border: '1px solid rgba(248,113,113,0.2)' }
            }
          >
            {settings.paused ? 'Resume' : 'Pause'}
          </button>
        </div>

        <div className="mt-5 pt-5" style={{ borderTop: '1px solid var(--border-2)' }}>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Heartbeat interval" sublabel="seconds between forced captures">
              <Input id="cap-interval" type="number" min={1} step={1}
                value={tuning.interval} onChange={e => setTuningField('interval', e.target.value)} />
            </Field>
            <Field label="Change cooldown" sublabel="min seconds between change captures">
              <Input id="cap-cooldown" type="number" min={0} step={0.5}
                value={tuning.cooldown} onChange={e => setTuningField('cooldown', e.target.value)} />
            </Field>
            <Field label="Max idle tick" sublabel="sampling backoff ceiling, seconds">
              <Input id="cap-idle-tick" type="number" min={1} step={1}
                value={tuning.idleTick} onChange={e => setTuningField('idleTick', e.target.value)} />
            </Field>
            <Field label="Similarity threshold" sublabel="phash duplicate cutoff (0.5–1.0)">
              <Input id="cap-threshold" type="number" min={0.51} max={1} step={0.01}
                value={tuning.threshold} onChange={e => setTuningField('threshold', e.target.value)} />
            </Field>
          </div>
          <div className="flex items-center justify-between mt-3">
            <span className="text-[12px]" style={{ color: 'var(--text-dim)' }}>
              Applied on the next daemon restart
            </span>
            <button
              onClick={() => saveTuning.mutate()}
              disabled={saveTuning.isPending}
              className="px-4 py-2 rounded-[9px] text-[13px] font-semibold transition-all disabled:opacity-40"
              style={{ background: 'var(--accent)', color: '#fff' }}
            >
              {saveTuning.isPending ? 'Saving…' : 'Save capture settings'}
            </button>
          </div>
        </div>
      </Section>

      {/* Chat Provider */}
      <Section title="Chat Provider">
        <Field label="Provider">
          <Select
            id="chat-type"
            options={CHAT_PROVIDER_OPTIONS}
            value={form.chatType}
            onChange={e => setField('chatType', e.target.value)}
          />
        </Field>
        <Field label="Base URL">
          <Input id="chat-url" value={form.chatUrl} onChange={e => setField('chatUrl', e.target.value)}
                 placeholder="e.g. http://localhost:11434/v1 (Ollama)" />
        </Field>
        <Field label="Model">
          <Input id="chat-model" value={form.chatModel} onChange={e => setField('chatModel', e.target.value)}
                 placeholder="e.g. GPT_5_2 / gpt-4o / claude-sonnet-4-6" />
        </Field>
        <Field label="API Key" sublabel={settings.has_chat_key ? '(keychain ✓)' : '(not set)'}>
          <Input type="password" value={form.chatKey} onChange={e => setField('chatKey', e.target.value)}
                 placeholder="Enter new key to update…" />
        </Field>
      </Section>

      {/* Embed Provider */}
      <Section title="Embed Provider">
        <Field label="Provider">
          <Select
            id="embed-type"
            options={EMBED_PROVIDER_OPTIONS}
            value={form.embedType}
            onChange={e => setField('embedType', e.target.value)}
          />
        </Field>
        <Field label="Base URL">
          <Input id="embed-url" value={form.embedUrl} onChange={e => setField('embedUrl', e.target.value)}
                 placeholder="e.g. http://localhost:11434 (Ollama)" />
        </Field>
        <Field label="Model">
          <Input id="embed-model" value={form.embedModel} onChange={e => setField('embedModel', e.target.value)}
                 placeholder="e.g. TEXT_EMBEDDING_3_LARGE / text-embedding-3-large" />
        </Field>
        <Field label="API Key" sublabel={settings.has_embed_key ? '(keychain ✓)' : '(not set)'}>
          <Input type="password" value={form.embedKey} onChange={e => setField('embedKey', e.target.value)}
                 placeholder="Enter new key to update…" />
        </Field>
        <button
          onClick={() => saveProviders.mutate()}
          disabled={saveProviders.isPending}
          className="px-5 py-2 rounded-[9px] text-[13px] font-semibold transition-all disabled:opacity-40"
          style={{ background: 'var(--accent)', color: '#fff' }}
        >
          {saveProviders.isPending ? 'Saving…' : 'Save Provider Settings'}
        </button>
      </Section>

      {/* Exclusions */}
      <Section title="Excluded Apps">
        <p className="text-[12px]" style={{ color: 'var(--text-dim)' }}>
          Apps listed here will never be captured — add password managers, banking apps, etc.
        </p>
        <div className="flex gap-2">
          <Input
            value={newApp}
            onChange={e => setNewApp(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && newApp.trim() && addExclusion.mutate()}
            placeholder="App name (e.g. 1Password)"
          />
          <button
            onClick={() => newApp.trim() && addExclusion.mutate()}
            disabled={addExclusion.isPending || !newApp.trim()}
            className="px-4 py-2 rounded-[9px] text-[13px] font-medium shrink-0 transition-all disabled:opacity-40"
            style={{ background: 'var(--accent)', color: '#fff' }}
          >
            Add
          </button>
        </div>
        {exclusions.length === 0 ? (
          <p className="text-[12px]" style={{ color: 'var(--text-dim)' }}>No excluded apps.</p>
        ) : (
          <ul className="space-y-1.5">
            {exclusions.map(ex => (
              <li
                key={ex.app_name}
                className="flex items-center justify-between rounded-[9px] px-3 py-2 border"
                style={{ background: 'var(--bg-surface-2)', borderColor: 'var(--border)' }}
              >
                <span className="text-[14px]" style={{ color: 'var(--text)' }}>{ex.app_name}</span>
                <button
                  onClick={() => removeExclusion.mutate(ex.app_name)}
                  className="text-[12px] transition-opacity hover:opacity-100 opacity-70"
                  style={{ color: 'var(--red)' }}
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
      </Section>

      {/* Screenshot Encryption */}
      <Section title="Screenshot Encryption">
        <p className="text-[12px]" style={{ color: 'var(--text-dim)' }}>
          Encrypt every screenshot at rest with AES-256-GCM. Password is stored in your OS keychain;
          if you forget it, all encrypted screenshots are unrecoverable.
        </p>

        {!settings.screenshot_encryption_enabled ? (
          // ── ENABLE FLOW ────────────────────────────────────────────────
          <>
            <div
              className="px-3 py-2 rounded-[9px] text-[12px] border"
              style={{ background: 'var(--bg-surface-2)', borderColor: 'var(--border)', color: 'var(--text-muted)' }}
            >
              Status: <span style={{ color: 'var(--text-dim)' }}>disabled</span> — screenshots are stored as plain JPEGs.
            </div>
            <Field label="Password" sublabel="(min 8 characters)">
              <Input type="password" value={encPwd} onChange={e => setEncPwd(e.target.value)}
                     placeholder="Choose a password…" autoComplete="new-password" />
            </Field>
            <Field label="Confirm Password">
              <Input type="password" value={encPwdConfirm} onChange={e => setEncPwdConfirm(e.target.value)}
                     placeholder="Re-enter password…" autoComplete="new-password" />
            </Field>
            <button
              onClick={() => {
                if (encPwd.length < 8) { flash('Password must be at least 8 characters'); return }
                if (encPwd !== encPwdConfirm) { flash('Passwords do not match'); return }
                enableEncryption.mutate()
              }}
              disabled={enableEncryption.isPending || !encPwd || !encPwdConfirm}
              className="px-5 py-2 rounded-[9px] text-[13px] font-semibold transition-all disabled:opacity-40"
              style={{ background: 'var(--accent)', color: '#fff' }}
            >
              {enableEncryption.isPending ? 'Enabling…' : 'Enable Encryption'}
            </button>
          </>
        ) : encMode === 'idle' ? (
          // ── ENABLED, IDLE ──────────────────────────────────────────────
          <>
            <div
              className="px-3 py-2 rounded-[9px] text-[12px] border"
              style={{ background: 'var(--green-bg)', borderColor: 'rgba(52,211,153,0.2)', color: 'var(--green)' }}
            >
              Status: <span className="font-semibold">enabled</span> — new screenshots are encrypted at capture time.
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setEncMode('change')}
                className="px-4 py-2 rounded-[9px] text-[13px] font-medium transition-all"
                style={{ background: 'var(--bg-surface-2)', color: 'var(--text)', border: '1px solid var(--border-2)' }}
              >
                Change Password
              </button>
              <button
                onClick={() => setEncMode('disable')}
                className="px-4 py-2 rounded-[9px] text-[13px] font-medium transition-all"
                style={{ background: 'var(--red-bg)', color: 'var(--red)', border: '1px solid rgba(248,113,113,0.2)' }}
              >
                Disable Encryption
              </button>
            </div>
          </>
        ) : encMode === 'change' ? (
          // ── CHANGE PASSWORD ────────────────────────────────────────────
          <>
            <Field label="Current Password">
              <Input type="password" value={encOldPwd} onChange={e => setEncOldPwd(e.target.value)}
                     autoComplete="current-password" />
            </Field>
            <Field label="New Password" sublabel="(min 8 characters)">
              <Input type="password" value={encNewPwd} onChange={e => setEncNewPwd(e.target.value)}
                     autoComplete="new-password" />
            </Field>
            <Field label="Confirm New Password">
              <Input type="password" value={encNewPwdConfirm} onChange={e => setEncNewPwdConfirm(e.target.value)}
                     autoComplete="new-password" />
            </Field>
            <div className="flex gap-2">
              <button
                onClick={() => {
                  if (encNewPwd.length < 8) { flash('Password must be at least 8 characters'); return }
                  if (encNewPwd !== encNewPwdConfirm) { flash('Passwords do not match'); return }
                  changeEncryption.mutate()
                }}
                disabled={changeEncryption.isPending || !encOldPwd || !encNewPwd}
                className="px-5 py-2 rounded-[9px] text-[13px] font-semibold transition-all disabled:opacity-40"
                style={{ background: 'var(--accent)', color: '#fff' }}
              >
                {changeEncryption.isPending ? 'Changing…' : 'Change Password'}
              </button>
              <button
                onClick={() => { setEncMode('idle'); setEncOldPwd(''); setEncNewPwd(''); setEncNewPwdConfirm('') }}
                className="px-4 py-2 rounded-[9px] text-[13px] font-medium transition-all"
                style={{ background: 'var(--bg-surface-2)', color: 'var(--text)', border: '1px solid var(--border-2)' }}
              >
                Cancel
              </button>
            </div>
          </>
        ) : (
          // ── DISABLE ────────────────────────────────────────────────────
          <>
            <p className="text-[12px]" style={{ color: 'var(--red)' }}>
              This will decrypt every existing screenshot and store them as plain JPEGs.
            </p>
            <Field label="Confirm with Current Password">
              <Input type="password" value={encDisablePwd} onChange={e => setEncDisablePwd(e.target.value)}
                     autoComplete="current-password" />
            </Field>
            <div className="flex gap-2">
              <button
                onClick={() => disableEncryption.mutate()}
                disabled={disableEncryption.isPending || !encDisablePwd}
                className="px-5 py-2 rounded-[9px] text-[13px] font-semibold transition-all disabled:opacity-40"
                style={{ background: 'var(--red)', color: '#fff' }}
              >
                {disableEncryption.isPending ? 'Disabling…' : 'Disable & Decrypt All'}
              </button>
              <button
                onClick={() => { setEncMode('idle'); setEncDisablePwd('') }}
                className="px-4 py-2 rounded-[9px] text-[13px] font-medium transition-all"
                style={{ background: 'var(--bg-surface-2)', color: 'var(--text)', border: '1px solid var(--border-2)' }}
              >
                Cancel
              </button>
            </div>
          </>
        )}
      </Section>

      {/* Storage */}
      <Section title="Storage">
        <p className="text-[13px]" style={{ color: 'var(--text-muted)' }}>
          Auto-purge: screenshots older than{' '}
          <span className="font-semibold" style={{ color: 'var(--text)' }}>{settings.purge_months} months</span>
          {' '}are automatically deleted.
        </p>
        <p className="text-[13px]" style={{ color: 'var(--text-muted)' }}>
          Data stored at{' '}
          <code
            className="px-1.5 py-0.5 rounded-[5px] font-mono text-[12px]"
            style={{ background: 'var(--bg-surface-2)', color: 'var(--accent)' }}
          >
            ~/.2brn/
          </code>
        </p>
      </Section>

      <Section title="Maintenance">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-[14px]" style={{ color: 'var(--text)' }}>Re-classify missed captures</div>
            <div className="text-[12px] mt-0.5" style={{ color: 'var(--text-dim)' }}>
              Re-runs AI inference for captures that were observed but never classified
              (provider outages, queue overflows). Uses your LLM provider.
            </div>
            <label className="flex items-center gap-2 mt-2 text-[12px] cursor-pointer" style={{ color: 'var(--text-muted)' }}>
              <input
                type="checkbox"
                checked={includeSparse}
                onChange={e => setIncludeSparse(e.target.checked)}
              />
              Include screens without readable text (videos, images — ~1 LLM call per window title)
            </label>
          </div>
          <button
            onClick={() => {
              if (window.confirm('Re-run AI inference for unclassified captures? This uses your LLM provider.')) {
                runBackfill.mutate()
              }
            }}
            disabled={runBackfill.isPending}
            className="px-4 py-2 rounded-[9px] text-[13px] font-semibold transition-all disabled:opacity-40 shrink-0"
            style={{ background: 'var(--accent)', color: '#fff' }}
          >
            {runBackfill.isPending ? 'Running…' : 'Run'}
          </button>
        </div>
        {backfillResult && (
          <div className="text-[12px] mt-2" style={{ color: 'var(--text-muted)' }}>{backfillResult}</div>
        )}

        <div className="mt-4 pt-4 flex items-start justify-between gap-4" style={{ borderTop: '1px solid var(--border-2)' }}>
          <div>
            <div className="text-[14px]" style={{ color: 'var(--text)' }}>Re-sync ChromaDB</div>
            <div className="text-[12px] mt-0.5" style={{ color: 'var(--text-dim)' }}>
              Re-embeds activities missing from the semantic search index (used by chat).
              Runs in the background.
            </div>
          </div>
          <button
            onClick={() => {
              if (window.confirm('Re-embed activities missing from ChromaDB? This uses your embedding provider.')) {
                runResync.mutate()
              }
            }}
            disabled={runResync.isPending}
            className="px-4 py-2 rounded-[9px] text-[13px] font-semibold transition-all disabled:opacity-40 shrink-0"
            style={{ background: 'var(--accent)', color: '#fff' }}
          >
            {runResync.isPending ? 'Running…' : 'Run'}
          </button>
        </div>
        {resyncResult && (
          <div className="text-[12px] mt-2" style={{ color: 'var(--text-muted)' }}>{resyncResult}</div>
        )}
      </Section>

      <Section title="JOPLIN INTEGRATION">
        <p className="text-[12px]" style={{ color: 'var(--text-dim)' }}>
          Sync your Joplin notes into 2brn's semantic memory so chat can recall them alongside
          screen activity. This reads the local Joplin SQLite DB every 60s — purely additive,
          no network calls, no writes to Joplin. To <em>send</em> things back to Joplin (mirror
          journals, append notes, etc.), add the Joplin MCP server in the{' '}
          <span className="font-medium" style={{ color: 'var(--text-muted)' }}>Plugins</span> section.
        </p>

        <div className="flex items-center justify-between pt-2">
          <div>
            <p className="text-[13px] font-medium" style={{ color: 'var(--text)' }}>Enable note embedding</p>
            <p className="text-[12px]" style={{ color: 'var(--text-dim)' }}>
              Embed all Joplin notes on startup and watch for changes.
            </p>
          </div>
          <button
            onClick={() => setField('joplinEnabled', !form.joplinEnabled)}
            className="relative inline-flex h-6 w-11 items-center rounded-full transition-colors"
            style={{ background: form.joplinEnabled ? 'var(--accent)' : 'var(--bg-surface-2)' }}
          >
            <span
              className="inline-block h-4 w-4 transform rounded-full transition-transform"
              style={{ background: 'var(--toggle-knob)', transform: form.joplinEnabled ? 'translateX(24px)' : 'translateX(4px)' }}
            />
          </button>
        </div>

        {form.joplinEnabled && (
          <Field
            label="Joplin database path"
            sublabel="(leave blank for default ~/.config/joplin-desktop/database.sqlite)"
          >
            <Input
              type="text"
              value={form.joplinDbPath}
              onChange={e => setField('joplinDbPath', e.target.value)}
              placeholder="/Users/me/.config/joplin-desktop/database.sqlite"
              spellCheck={false}
            />
          </Field>
        )}
      </Section>

      {/* Daemon */}
      <Section title="Daemon">
        {daemonOwned === false ? (
          <p className="text-[12px]" style={{ color: 'var(--text-dim)' }}>
            Daemon was started externally — restart not available.
          </p>
        ) : (
          <div className="flex items-center justify-between">
            <div>
              <div className="text-[14px]" style={{ color: 'var(--text)' }}>
                Restart daemon
              </div>
              <div className="text-[12px] mt-0.5" style={{ color: 'var(--text-dim)' }}>
                Stops and restarts the background process
              </div>
            </div>
            <button
              onClick={handleRestartDaemon}
              disabled={restartState === 'restarting' || daemonOwned === null}
              className="px-4 py-2 rounded-[9px] text-[13px] font-medium transition-all disabled:opacity-40"
              style={{ background: 'var(--amber-bg, #fef3c7)', color: 'var(--amber, #d97706)', border: '1px solid rgba(217,119,6,0.2)' }}
            >
              {restartState === 'restarting' ? 'Restarting…' : 'Restart Daemon'}
            </button>
          </div>
        )}
      </Section>
    </div>
  )
}
