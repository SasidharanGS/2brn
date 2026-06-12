export const queryKeys = {
  status: () => ['status'] as const,
  insightsSummary: (date: string, period: string) =>
    ['insights', 'summary', period, date] as const,
  activities: (date: string) => ['activities', date] as const,
  sessions: (date: string) => ['sessions', date] as const,
  captures: (date: string) => ['captures', date] as const,
  journal: (date: string) => ['journal', date] as const,
  blog: (date: string) => ['blog', date] as const,
  settings: () => ['settings'] as const,
  exclusions: () => ['settings', 'exclusions'] as const,
  instructions: () => ['instructions'] as const,
  plugins: () => ['plugins'] as const,
  pluginRules: (pluginId: number | null) => ['plugin-rules', pluginId ?? 0] as const,
  pluginTools: (pluginId: number | null) => ['plugin-tools', pluginId ?? 0] as const,
  ruleExecutions: (ruleId: number | null) => ['rule-executions', ruleId ?? 0] as const,
} as const
