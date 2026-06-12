// Minimal-skin state encoding — intensity, never hue.
// Productivity state maps onto the --ink-0…4 ramp (darker = more focus);
// categories are neutral pills. The one accent (muted red) is reserved for
// live/important cues and never used here.

/** Productivity state → ramp level (0–4). */
export const STATE_INK: Record<string, number> = {
  deep_work: 4,
  focused: 4,
  productive: 3,
  'in-meeting': 2,
  communication: 2,
  chilling: 1,
  distracted: 1,
  procrastinating: 1,
  idle: 0,
}

export function stateInk(state: string | null | undefined): number {
  return STATE_INK[state ?? ''] ?? 0
}

/** CSS color for a state's ramp step. */
export function inkVar(level: number): string {
  return `var(--ink-${Math.max(0, Math.min(4, level))})`
}
