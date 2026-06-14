import type { ActivityRecord } from '../api/types'

export interface HourGroups {
  /** hour (0–23) → that hour's activities, newest-first */
  byHour: Map<number, ActivityRecord[]>
  /** hours that actually have activity, newest-first (descending) */
  activeHours: number[]
  /** contiguous hour span from latest→earliest, for the navigation rail */
  railHours: number[]
}

/**
 * Group the (already date-filtered) feed by local hour, **newest-first**.
 *
 * Both skins' timelines consume this so they render in identical order — the
 * latest entry sits at the very top, hours descend below it, and the rail spans
 * the active range. Presentation differs per skin; ordering must not.
 */
export function groupActivitiesByHour(filtered: ActivityRecord[]): HourGroups {
  const byHour = new Map<number, ActivityRecord[]>()
  for (const a of filtered) {
    const h = new Date(a.started_at).getHours()
    const bucket = byHour.get(h)
    if (bucket) bucket.push(a)
    else byHour.set(h, [a])
  }
  // Newest activity first within each hour.
  for (const bucket of byHour.values()) bucket.sort((a, b) => b.started_at.localeCompare(a.started_at))

  const activeHours = [...byHour.keys()].sort((x, y) => y - x) // latest hour first
  const railHours: number[] = []
  if (activeHours.length) {
    const hi = activeHours[0]
    const lo = activeHours[activeHours.length - 1]
    for (let h = hi; h >= lo; h--) railHours.push(h)
  }
  return { byHour, activeHours, railHours }
}

/** Whole-hour label for the rail + sticky headings, e.g. "09:00 am". */
export function fmtHour(h: number): string {
  const ap = h < 12 ? 'am' : 'pm'
  const hh = h % 12 === 0 ? 12 : h % 12
  return `${String(hh).padStart(2, '0')}:00 ${ap}`
}
