import { useState, useEffect } from 'react'
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
  const [chatType, setChatType]     = useState('')
  const [chatUrl, setChatUrl]       = useState('')
  const [chatModel, setChatModel]   = useState('')
  const [chatKey, setChatKey]       = useState('')
  const [embedType, setEmbedType]   = useState('')
  const [embedUrl, setEmbedUrl]     = useState('')
  const [embedModel, setEmbedModel] = useState('')
  const [embedKey, setEmbedKey]     = useState('')
  const [newApp, setNewApp]         = useState('')
  const [saveMessage, setSaveMessage]     = useState('')
  const [blogMirror, setBlogMirror] = useState(true)

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
    if (settings && !chatUrl) {
      setChatType(settings.chat_provider.type)
      setChatUrl(settings.chat_provider.base_url)
      setChatModel(settings.chat_provider.model)
      setEmbedType(settings.embed_provider.type)
      setEmbedUrl(settings.embed_provider.base_url)
      setEmbedModel(settings.embed_provider.model)
      setBlogMirror(settings.blog_mirror_enabled ?? true)
    }
  }, [settings?.chat_provider?.base_url]) // eslint-disable-line

  const flash = (msg: string) => { setSaveMessage(msg); setTimeout(() => setSaveMessage(''), 3000) }

  const saveProviders = useMutation({
    mutationFn: () => api.updateSettings({
      chat_provider: {
        type: chatType, base_url: chatUrl, model: chatModel,
        ...(chatKey ? { api_key: chatKey } : {}),
      },
      embed_provider: {
        type: embedType, base_url: embedUrl, model: embedModel,
        ...(embedKey ? { api_key: embedKey } : {}),
      },
      blog_mirror_enabled: blogMirror,
    }),
    onSuccess: () => {
      setChatKey(''); setEmbedKey('')
      flash('Settings saved')
      qc.invalidateQueries({ queryKey: queryKeys.settings() })
    },
    onError: () => flash('Failed to save'),
  })

  const togglePause = useMutation({
    mutationFn: () => api.setPaused(!settings?.paused),
    onSuccess:  () => qc.invalidateQueries({ queryKey: queryKeys.settings() }),
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
            onClick={() => togglePause.mutate()}
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
      </Section>

      {/* Chat Provider */}
      <Section title="Chat Provider">
        <Field label="Provider">
          <Select
            options={CHAT_PROVIDER_OPTIONS}
            value={chatType}
            onChange={e => setChatType(e.target.value)}
          />
        </Field>
        <Field label="Base URL">
          <Input value={chatUrl} onChange={e => setChatUrl(e.target.value)}
                 placeholder="e.g. http://localhost:11434/v1 (Ollama)" />
        </Field>
        <Field label="Model">
          <Input value={chatModel} onChange={e => setChatModel(e.target.value)}
                 placeholder="e.g. GPT_5_2 / gpt-4o / claude-sonnet-4-6" />
        </Field>
        <Field label="API Key" sublabel={settings.has_chat_key ? '(keychain ✓)' : '(not set)'}>
          <Input type="password" value={chatKey} onChange={e => setChatKey(e.target.value)}
                 placeholder="Enter new key to update…" />
        </Field>
      </Section>

      {/* Embed Provider */}
      <Section title="Embed Provider">
        <Field label="Provider">
          <Select
            options={EMBED_PROVIDER_OPTIONS}
            value={embedType}
            onChange={e => setEmbedType(e.target.value)}
          />
        </Field>
        <Field label="Base URL">
          <Input value={embedUrl} onChange={e => setEmbedUrl(e.target.value)}
                 placeholder="e.g. http://localhost:11434 (Ollama)" />
        </Field>
        <Field label="Model">
          <Input value={embedModel} onChange={e => setEmbedModel(e.target.value)}
                 placeholder="e.g. TEXT_EMBEDDING_3_LARGE / text-embedding-3-large" />
        </Field>
        <Field label="API Key" sublabel={settings.has_embed_key ? '(keychain ✓)' : '(not set)'}>
          <Input type="password" value={embedKey} onChange={e => setEmbedKey(e.target.value)}
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

      <div className="rounded-[12px] border p-5" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
        <h2 className="text-[14px] font-semibold mb-4" style={{ color: 'var(--text)' }}>Blog</h2>
        <div className="space-y-4">
          <p className="text-[12px]" style={{ color: 'var(--text-dim)' }}>
            Dev log entries are generated nightly at 21:00.
          </p>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[13px] font-medium" style={{ color: 'var(--text)' }}>Mirror to Joplin</p>
              <p className="text-[12px]" style={{ color: 'var(--text-dim)' }}>Save blog posts to "Blog Posts" notebook</p>
            </div>
            <button
              onClick={() => setBlogMirror(v => !v)}
              className="relative inline-flex h-6 w-11 items-center rounded-full transition-colors"
              style={{ background: blogMirror ? 'var(--accent)' : 'var(--bg-surface-2)' }}
            >
              <span
                className="inline-block h-4 w-4 transform rounded-full transition-transform"
                style={{ background: 'var(--toggle-knob)', transform: blogMirror ? 'translateX(24px)' : 'translateX(4px)' }}
              />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
