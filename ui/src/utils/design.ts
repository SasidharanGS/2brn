import type React from 'react'

// Centralised colour helpers — single source of truth for all category and state chips.

export const CATEGORY_CHIP: Record<string, { bg: string; text: string; dot: string }> = {
  work:          { bg: 'rgba(96,165,250,0.12)',  text: '#60a5fa', dot: '#60a5fa' },
  research:      { bg: 'rgba(192,132,252,0.12)', text: '#c084fc', dot: '#c084fc' },
  play:          { bg: 'rgba(52,211,153,0.12)',  text: '#34d399', dot: '#34d399' },
  learning:      { bg: 'rgba(251,191,36,0.12)',  text: '#fbbf24', dot: '#fbbf24' },
  communication: { bg: 'rgba(45,212,191,0.12)',  text: '#2dd4bf', dot: '#2dd4bf' },
  creative:      { bg: 'rgba(244,114,182,0.12)', text: '#f472b6', dot: '#f472b6' },
  admin:         { bg: 'rgba(148,163,184,0.12)', text: '#94a3b8', dot: '#94a3b8' },
  other:         { bg: 'rgba(100,116,139,0.12)', text: '#64748b', dot: '#64748b' },
  // Screen time with no classified activity (sparse OCR text, e.g. video) —
  // deliberately dimmer than every real category.
  unclassified:  { bg: 'rgba(100,116,139,0.08)', text: '#566073', dot: '#475569' },
}

export const STATE_CHIP: Record<string, { bg: string; text: string }> = {
  productive:      { bg: 'rgba(52,211,153,0.12)',  text: '#34d399' },
  focused:         { bg: 'rgba(52,211,153,0.12)',  text: '#34d399' },
  chilling:        { bg: 'rgba(96,165,250,0.12)',  text: '#60a5fa' },
  procrastinating: { bg: 'rgba(248,113,113,0.12)', text: '#f87171' },
  distracted:      { bg: 'rgba(251,146,60,0.12)',  text: '#fb923c' },
  'in-meeting':    { bg: 'rgba(192,132,252,0.12)', text: '#c084fc' },
  idle:            { bg: 'rgba(100,116,139,0.12)', text: '#64748b' },
}

// Re-export flat hex map for recharts Cell fill compatibility
export const STATE_COLORS: Record<string, string> = Object.fromEntries(
  Object.entries(STATE_CHIP).map(([k, v]) => [k, v.text])
)

export function categoryChip(cat: string | null | undefined) {
  return CATEGORY_CHIP[cat ?? 'other'] ?? CATEGORY_CHIP.other
}

export function stateChip(state: string | null | undefined) {
  return STATE_CHIP[state ?? 'idle'] ?? STATE_CHIP.idle
}

/** Inline style object for a coloured dot */
export function dotStyle(cat: string | null | undefined): React.CSSProperties {
  return { background: categoryChip(cat).dot }
}
