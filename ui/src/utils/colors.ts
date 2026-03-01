/** Shared colour maps for task categories and productivity states.
 *  Single source of truth — import in Timeline, Insights, and anywhere else needed.
 */

export const CATEGORY_COLORS: Record<string, string> = {
  work: '#3b82f6',
  research: '#8b5cf6',
  play: '#22c55e',
  learning: '#f59e0b',
  communication: '#06b6d4',
  creative: '#ec4899',
  admin: '#64748b',
  other: '#475569',
}

export const STATE_COLORS: Record<string, string> = {
  productive: '#22c55e',
  focused: '#86efac',
  chilling: '#60a5fa',
  procrastinating: '#ef4444',
  distracted: '#f97316',
  'in-meeting': '#a78bfa',
  idle: '#64748b',
}
