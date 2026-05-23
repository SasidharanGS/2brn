export interface DaemonStatus {
  status: 'capturing' | 'paused' | 'error'
  capture_count_today: number
  last_captured_at: string | null
  daemon_version: string
}

export interface CaptureRecord {
  id: number
  captured_at: string
  app_name: string | null
  window_title: string | null
  file_path: string | null
  trigger: string | null
  monitor_index: number | null
}

export interface ActivityRecord {
  id: number
  capture_id: number | null
  started_at: string
  ended_at: string | null
  summary: string | null
  tags: string | null
  task_category: string | null
  task_category_confidence: number | null
  productivity_state: string | null
  productivity_confidence: number | null
  category_overridden_by_user: boolean
}

export interface JournalEntry {
  date: string
  content: string | null
  generated_at: string | null
  edited_by_user: boolean
}

export interface BlogPost {
  date: string
  content: string | null
  generated_at: string | null
  edited_by_user: boolean
}

export interface DailyInsights {
  date: string
  categories: { task_category: string; count: number; avg_confidence: number }[]
  productivity_states: { productivity_state: string; count: number }[]
  top_apps: { app_name: string; count: number }[]
}

export interface ProviderConfig {
  type: string
  base_url: string
  model: string
  extra_headers?: Record<string, string>
}

export interface AppSettings {
  chat_provider: ProviderConfig
  embed_provider: ProviderConfig
  has_chat_key: boolean
  has_embed_key: boolean
  capture_interval_seconds: number
  purge_months: number
  paused: boolean
  blog_mirror_enabled: boolean
}

export interface ProviderConfigUpdate {
  type?: string
  base_url?: string
  model?: string
  extra_headers?: Record<string, string>
  api_key?: string
}

export interface SettingsUpdateRequest {
  chat_provider?: ProviderConfigUpdate
  embed_provider?: ProviderConfigUpdate
  capture_interval_seconds?: number
  purge_months?: number
  blog_mirror_enabled?: boolean
}

export interface AppExclusion {
  app_name: string
  added_at: string
}

export interface UserInstruction {
  id: number
  title: string
  body: string
  enabled: boolean
  created_at: string
}

export interface LogLine {
  ts: string  // "HH:MM:SS"
  level: 'INFO' | 'WARNING' | 'ERROR' | 'DEBUG'
  msg: string
}

export interface DebugStatus {
  daemon: {
    status: string
    capture_count_today: number
    last_captured_at: string | null
    paused: boolean
  }
  gateway: {
    url: string
    reachable: boolean
    model: string
  }
  chroma: {
    activity_memories: number
    note_memories: number
  }
  last_error: { ts: string; msg: string } | null
}

declare global {
  interface Window {
    electronAPI: {
      getDaemonPort: () => Promise<number>
      getPlatform: () => Promise<string>
      onDaemonStatus: (callback: (status: string) => void) => void
      getTheme: () => Promise<'dark' | 'light'>
      onThemeChanged: (callback: (theme: 'dark' | 'light') => void) => void
    }
  }
}
