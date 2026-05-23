export const queryKeys = {
  status: () => ['status'] as const,
  dailyInsights: (date: string) => ['insights', 'daily', date] as const,
  activities: (date: string) => ['activities', date] as const,
  captures: (date: string) => ['captures', date] as const,
  journal: (date: string) => ['journal', date] as const,
  blog: (date: string) => ['blog', date] as const,
  settings: () => ['settings'] as const,
  exclusions: () => ['settings', 'exclusions'] as const,
} as const
