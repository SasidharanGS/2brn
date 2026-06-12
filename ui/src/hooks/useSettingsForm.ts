import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { queryKeys } from '../api/queryKeys'

// ── Provider catalogues ──────────────────────────────────────────────────────

export const CHAT_PROVIDER_OPTIONS = [
  { value: 'openai_compatible', label: 'OpenAI-Compatible (LM Studio, local gateway, etc.)' },
  { value: 'openai',            label: 'OpenAI' },
  { value: 'anthropic',         label: 'Anthropic' },
  { value: 'azure',             label: 'Azure OpenAI' },
  { value: 'ollama',            label: 'Ollama (local)' },
  { value: 'groq',              label: 'Groq' },
  { value: 'together',          label: 'Together AI' },
  { value: 'cohere',            label: 'Cohere' },
]

export const EMBED_PROVIDER_OPTIONS = [
  { value: 'custom', label: 'Custom (non-standard format, e.g. enterprise gateways)' },
  { value: 'openai', label: 'OpenAI-Compatible (OpenAI, Azure, Ollama, etc.)' },
]

export type SettingsFormState = {
  chatType: string; chatUrl: string; chatModel: string; chatKey: string
  embedType: string; embedUrl: string; embedModel: string; embedKey: string
  joplinEnabled: boolean; joplinDbPath: string
}

// Capture tuning fields are kept as strings while editing; parsed on save.
export type TuningState = { interval: string; cooldown: string; idleTick: string; threshold: string }

export type EncryptionMode = 'idle' | 'change' | 'disable'

/** All Settings-screen data, form state, and mutations — presentation-free. */
export function useSettingsForm() {
  const qc = useQueryClient()
  const [form, setForm] = useState<SettingsFormState>({
    chatType: '', chatUrl: '', chatModel: '', chatKey: '',
    embedType: '', embedUrl: '', embedModel: '', embedKey: '',
    joplinEnabled: false, joplinDbPath: '',
  })
  const setField = <K extends keyof SettingsFormState>(key: K, value: SettingsFormState[K]) =>
    setForm(prev => ({ ...prev, [key]: value }))
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
  const [encMode, setEncMode]       = useState<EncryptionMode>('idle')

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

  return {
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
  }
}
