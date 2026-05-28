import type {
  DaemonStatus, CaptureRecord, ActivityRecord, JournalEntry, BlogPost,
  DailyInsights, InsightsSummary, InsightsPeriod,
  AppSettings, SettingsUpdateRequest, AppExclusion, UserInstruction, LogLine, DebugStatus,
  Plugin, PluginRule, PluginTool, RuleExecution, PluginCreate, PluginUpdate, RuleCreate, RuleUpdate,
} from './types'

const BASE_URL = 'http://127.0.0.1:7842'

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`)
  if (!res.ok) throw new ApiError(res.status, `GET ${path} failed: ${res.status}`)
  return res.json()
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new ApiError(res.status, `POST ${path} failed: ${res.status}`)
  return res.json()
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new ApiError(res.status, `PUT ${path} failed: ${res.status}`)
  return res.json()
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, { method: 'DELETE' })
  if (!res.ok) throw new ApiError(res.status, `DELETE ${path} failed: ${res.status}`)
  return res.json()
}

export const api = {
  getStatus: () => get<DaemonStatus>('/status'),
  getCaptures: (date: string) => get<CaptureRecord[]>(`/captures?date=${date}`),
  getActivities: (params: { date?: string; task_category?: string; productivity_state?: string }) => {
    const q = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v) as [string, string][]
    )
    return get<ActivityRecord[]>(`/activities?${q}`)
  },
  overrideActivity: (id: number, task_category: string, productivity_state: string) =>
    fetch(`${BASE_URL}/activities/${id}/override`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task_category, productivity_state }),
    }).then(r => r.json()),
  getJournal: (date: string) => get<JournalEntry>(`/journal/${date}`),
  generateJournal: (date: string) => post(`/journal/${date}/generate`),
  updateJournal: (date: string, content: string) => put(`/journal/${date}`, { content }),
  getBlogPost: (date: string) => get<BlogPost>(`/blog/${date}`).catch((e: unknown) => {
    if (e instanceof ApiError && e.status === 404) return null
    throw e
  }),
  generateBlogPost: (date: string) => post<{ ok: boolean; generated: boolean }>(`/blog/${date}/generate`),
  updateBlogPost: (date: string, content: string) => put<{ ok: boolean }>(`/blog/${date}`, { content }),
  getSettings: () => get<AppSettings>('/settings'),
  updateSettings: (body: SettingsUpdateRequest) => put('/settings', body),
  setPaused: (paused: boolean) => post(`/settings/paused?paused=${paused}`),
  getExclusions: () => get<AppExclusion[]>('/settings/exclusions'),
  addExclusion: (app_name: string) => post('/settings/exclusions', { app_name }),
  removeExclusion: (app_name: string) => del(`/settings/exclusions/${encodeURIComponent(app_name)}`),

  // Screenshot encryption
  setScreenshotPassword: (password: string, encrypt_existing = true) =>
    post<{ ok: boolean; message: string }>('/settings/screenshot-password', { password, encrypt_existing }),
  changeScreenshotPassword: (old_password: string, new_password: string) =>
    put<{ ok: boolean; message: string }>('/settings/screenshot-password', { old_password, new_password }),
  disableScreenshotPassword: (password: string, decrypt_existing = true) =>
    fetch(`${BASE_URL}/settings/screenshot-password`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password, decrypt_existing }),
    }).then(async r => {
      if (!r.ok) throw new ApiError(r.status, `DELETE failed: ${r.status}`)
      return r.json() as Promise<{ ok: boolean; message: string }>
    }),

  getDailyInsights: (date: string) => get<DailyInsights>(`/insights/daily?date=${date}`),
  getInsightsSummary: (date: string, period: InsightsPeriod = 'day') =>
    get<InsightsSummary>(`/insights/summary?date=${date}&period=${period}`),
  getLogs: (level?: string, limit?: number) => {
    const q = new URLSearchParams()
    if (level) q.set('level', level)
    if (limit) q.set('limit', String(limit))
    return get<{ lines: LogLine[] }>(`/logs?${q}`)
  },
  getDebugStatus: () => get<DebugStatus>('/debug/status'),

  listInstructions: () => get<UserInstruction[]>('/instructions'),
  createInstruction: (title: string, body: string, enabled = true) =>
    post<UserInstruction>('/instructions', { title, body, enabled }),
  updateInstruction: (id: number, patch: Partial<Pick<UserInstruction, 'title' | 'body' | 'enabled'>>) =>
    put<UserInstruction>(`/instructions/${id}`, patch),
  deleteInstruction: (id: number) =>
    fetch(`${BASE_URL}/instructions/${id}`, { method: 'DELETE' }).then(() => undefined),

  // ── Plugins ─────────────────────────────────────────────────────────────────
  listPlugins: () => get<Plugin[]>('/plugins'),
  createPlugin: (body: PluginCreate) => post<Plugin>('/plugins', body),
  updatePlugin: (id: number, body: PluginUpdate) => put<Plugin>(`/plugins/${id}`, body),
  deletePlugin: (id: number) =>
    fetch(`${BASE_URL}/plugins/${id}`, { method: 'DELETE' }).then(r => {
      if (!r.ok) throw new Error(`DELETE failed: ${r.status}`)
    }),
  listPluginTools: (id: number) => get<PluginTool[]>(`/plugins/${id}/tools`),

  listPluginRules: (plugin_id?: number) => {
    const q = plugin_id ? `?plugin_id=${plugin_id}` : ''
    return get<PluginRule[]>(`/plugin-rules${q}`)
  },
  createPluginRule: (body: RuleCreate) => post<PluginRule>('/plugin-rules', body),
  updatePluginRule: (id: number, body: RuleUpdate) => put<PluginRule>(`/plugin-rules/${id}`, body),
  deletePluginRule: (id: number) =>
    fetch(`${BASE_URL}/plugin-rules/${id}`, { method: 'DELETE' }).then(r => {
      if (!r.ok) throw new Error(`DELETE failed: ${r.status}`)
    }),
  reparsePluginRule: (id: number) => post<PluginRule>(`/plugin-rules/${id}/reparse`),
  runPluginRule: (id: number) =>
    post<{ ok: boolean; result?: Record<string, unknown>; error?: string }>(`/plugin-rules/${id}/run`),
  listRuleExecutions: (id: number, limit = 50) =>
    get<RuleExecution[]>(`/plugin-rules/${id}/executions?limit=${limit}`),

  chatStream: async function* (question: string, date_filter?: string, category_filter?: string, signal?: AbortSignal) {
    const res = await fetch(`${BASE_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, date_filter, category_filter }),
      signal,
    })
    if (!res.body) return
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') return
          try {
            const parsed = JSON.parse(data)
            if (parsed.chunk) yield parsed.chunk as string
          } catch { /* skip malformed */ }
        }
      }
    }
  }
}
