import type {
  DaemonStatus, CaptureRecord, ActivityRecord, JournalEntry, BlogPost,
  DailyInsights, AppSettings, SettingsUpdateRequest, AppExclusion, UserInstruction, LogLine, DebugStatus
} from './types'

const BASE_URL = 'http://127.0.0.1:7842'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`)
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`)
  return res.json()
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`)
  return res.json()
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`PUT ${path} failed: ${res.status}`)
  return res.json()
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`DELETE ${path} failed: ${res.status}`)
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
  getBlogPost: (date: string) => get<BlogPost>(`/blog/${date}`).catch((e: Error) => {
    if (e.message.includes('404')) return null
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
  getDailyInsights: (date: string) => get<DailyInsights>(`/insights/daily?date=${date}`),
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
