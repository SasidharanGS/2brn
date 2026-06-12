import type {
  DaemonStatus, CaptureRecord, ActivityRecord, JournalEntry, BlogPost,
  DailyInsights, InsightsSummary, InsightsPeriod, SessionsResponse,
  AppSettings, SettingsUpdateRequest, AppExclusion, UserInstruction, LogLine, DebugStatus,
  Plugin, PluginRule, PluginTool, RuleExecution, PluginCreate, PluginUpdate, RuleCreate, RuleUpdate,
} from './types'

let BASE_URL = 'http://127.0.0.1:7842'

/** Point the client at the daemon port reported by the Electron bridge (with a
 *  fallback to the default). Called once at startup, before any request. */
export async function initApiBase(): Promise<void> {
  try {
    const port = await window.electronAPI?.getDaemonPort?.()
    if (port) BASE_URL = `http://127.0.0.1:${port}`
  } catch {
    /* keep the default */
  }
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

// The daemon requires a loopback bearer token (written to ~/.2brn/api_token and
// exposed to the renderer via the Electron bridge). Fetch it once, then attach
// it to every request.
let _tokenPromise: Promise<string> | null = null
function apiToken(): Promise<string> {
  if (_tokenPromise) return _tokenPromise
  const getter = window.electronAPI?.getApiToken
  const p = (getter ? getter() : Promise.resolve('')).catch(() => '')
  _tokenPromise = p
  // Don't cache an empty token: at startup the daemon may not have written the
  // token file yet. Forgetting it lets the next request retry instead of being
  // wedged at 401 until a reload.
  p.then((t) => { if (!t && _tokenPromise === p) _tokenPromise = null })
  return p
}

async function authedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await apiToken()
  const headers = new Headers(init.headers)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  return fetch(`${BASE_URL}${path}`, { ...init, headers })
}

async function get<T>(path: string): Promise<T> {
  const res = await authedFetch(path)
  if (!res.ok) throw new ApiError(res.status, `GET ${path} failed: ${res.status}`)
  return res.json()
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await authedFetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new ApiError(res.status, `POST ${path} failed: ${res.status}`)
  return res.json()
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await authedFetch(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new ApiError(res.status, `PUT ${path} failed: ${res.status}`)
  return res.json()
}

async function del<T>(path: string): Promise<T> {
  const res = await authedFetch(path, { method: 'DELETE' })
  if (!res.ok) throw new ApiError(res.status, `DELETE ${path} failed: ${res.status}`)
  return res.json()
}

async function patch<T>(path: string, body?: unknown): Promise<T> {
  const res = await authedFetch(path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new ApiError(res.status, `PATCH ${path} failed: ${res.status}`)
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
    patch<ActivityRecord>(`/activities/${id}/override`, { task_category, productivity_state }),
  getSessions: (date: string) => get<SessionsResponse>(`/sessions?date=${date}`),
  getJournal: (date: string) => get<JournalEntry>(`/journal/${date}`).catch((e: unknown) => {
    if (e instanceof ApiError && e.status === 404) return null
    throw e
  }),
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
    authedFetch('/settings/screenshot-password', {
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
    authedFetch(`/instructions/${id}`, { method: 'DELETE' }).then(r => {
      if (!r.ok) throw new ApiError(r.status, `DELETE /instructions/${id} failed: ${r.status}`)
    }),

  // ── Plugins ─────────────────────────────────────────────────────────────────
  listPlugins: () => get<Plugin[]>('/plugins'),
  createPlugin: (body: PluginCreate) => post<Plugin>('/plugins', body),
  updatePlugin: (id: number, body: PluginUpdate) => put<Plugin>(`/plugins/${id}`, body),
  deletePlugin: (id: number) =>
    authedFetch(`/plugins/${id}`, { method: 'DELETE' }).then(r => {
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
    authedFetch(`/plugin-rules/${id}`, { method: 'DELETE' }).then(r => {
      if (!r.ok) throw new Error(`DELETE failed: ${r.status}`)
    }),
  reparsePluginRule: (id: number) => post<PluginRule>(`/plugin-rules/${id}/reparse`),
  runPluginRule: (id: number) =>
    post<{ ok: boolean; result?: Record<string, unknown>; error?: string }>(`/plugin-rules/${id}/run`),
  listRuleExecutions: (id: number, limit = 50) =>
    get<RuleExecution[]>(`/plugin-rules/${id}/executions?limit=${limit}`),

  chatStream: async function* (question: string, date_filter?: string, category_filter?: string, signal?: AbortSignal) {
    const res = await authedFetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, date_filter, category_filter }),
      signal,
    })
    if (!res.ok) throw new ApiError(res.status, `POST /chat failed: ${res.status}`)
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
