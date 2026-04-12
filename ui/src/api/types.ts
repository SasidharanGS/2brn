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

// ── Insights summary (Day / Week / Month) ─────────────────────────────────────

export type InsightsPeriod = 'day' | 'week' | 'month'

export interface InsightsCategoryBucket {
  task_category: string
  count: number
  total_minutes: number
  avg_confidence: number
}

export interface InsightsStateBucket {
  productivity_state: string
  count: number
  total_minutes: number
}

export interface InsightsAppBucket {
  app_name: string
  count: number
  total_minutes: number
}

export interface HeatmapCell {
  hour: number  // 0–23
  total_minutes: number
  dominant_state: string | null
  by_state_minutes: Record<string, number>
}

export interface ComparisonMetric {
  current_minutes: number
  baseline_minutes: number
}

export interface InsightsComparison {
  baseline_label: string  // "7-day average" | "4-week average" | "3-month average"
  active: ComparisonMetric
  productive: ComparisonMetric
  distracted: ComparisonMetric
}

export interface RecurringActivity {
  canonical_summary: string
  total_minutes: number
  session_count: number
  variant_count: number
}

export interface InsightsSummary {
  period: InsightsPeriod
  date: string
  range: { start: string; end: string; span_days: number }
  interval_seconds: number
  categories: InsightsCategoryBucket[]
  productivity_states: InsightsStateBucket[]
  top_apps: InsightsAppBucket[]
  hourly_heatmap: HeatmapCell[]
  comparison: InsightsComparison
  recurring_activities: RecurringActivity[]
}

export interface ProviderConfig {
  type: string
  base_url: string
  model: string
  extra_headers?: Record<string, string>
}

export interface ScheduleConfig {
  hour: number
  minute: number
}

export interface BlogScheduleConfig {
  frequency: 'daily' | 'monthly' | 'weekly'
  hour: number
  minute: number
  day: number
  days_of_week: string[]
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
  screenshot_encryption_enabled: boolean
  journal_schedule: ScheduleConfig
  blog_schedule: BlogScheduleConfig
  joplin_enabled: boolean
  joplin_db_path: string
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
  journal_schedule?: ScheduleConfig
  blog_schedule?: BlogScheduleConfig
  joplin_enabled?: boolean
  joplin_db_path?: string
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

// ── Plugins ───────────────────────────────────────────────────────────────────

export interface Plugin {
  id: number
  name: string
  command: string
  args: string[]
  env_keys: string[]
  enabled: boolean
  created_at: string
  last_health_at: string | null
  last_health_ok: boolean | null
  last_health_error: string | null
}

export interface PluginRule {
  id: number
  plugin_id: number
  title: string
  rule_text: string
  enabled: boolean
  trigger: string
  tool_name: string | null
  args_template: Record<string, unknown> | null
  parse_status: 'pending' | 'ok' | 'error'
  parse_error: string | null
  parsed_at: string | null
  created_at: string
}

export interface PluginTool {
  name: string
  description: string
  input_schema: Record<string, unknown>
}

export interface RuleExecution {
  id: number
  rule_id: number
  started_at: string
  ended_at: string | null
  status: 'ok' | 'error' | 'timeout' | 'running'
  error: string | null
  payload: Record<string, unknown> | null
  result: Record<string, unknown> | null
}

export interface PluginCreate {
  name: string
  command: string
  args?: string[]
  env?: Record<string, string>  // values are stashed in keychain; only key names persist
}

export interface PluginUpdate {
  command?: string
  args?: string[]
  env?: Record<string, string>
  enabled?: boolean
}

export interface RuleCreate {
  plugin_id: number
  title: string
  rule_text: string
  enabled?: boolean
}

export interface RuleUpdate {
  title?: string
  rule_text?: string
  enabled?: boolean
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
