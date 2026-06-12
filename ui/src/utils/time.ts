/** "3h 12m" / "45m" / "<1m" — compact duration for block-time displays. */
export function fmtDur(seconds: number): string {
  const m = Math.round(seconds / 60)
  if (m < 1) return '<1m'
  const h = Math.floor(m / 60)
  const rem = m % 60
  if (h === 0) return `${m}m`
  return rem === 0 ? `${h}h` : `${h}h ${rem}m`
}
