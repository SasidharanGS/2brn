import { describe, expect, it } from 'vitest'
import { groupActivitiesByHour } from '../timeline'
import type { ActivityRecord } from '../../api/types'

// Local-time ISO strings (no TZ suffix) so getHours() is stable across runners.
function act(id: number, started_at: string): ActivityRecord {
  return {
    id,
    capture_id: null,
    started_at,
    summary: null,
    tags: null,
    task_category: null,
    task_category_confidence: null,
    productivity_state: null,
    productivity_confidence: null,
    category_overridden_by_user: false,
  }
}

describe('groupActivitiesByHour', () => {
  it('buckets by local hour, newest-first, with a contiguous rail', () => {
    const { byHour, activeHours, railHours } = groupActivitiesByHour([
      act(1, '2026-06-14T09:05:00'),
      act(2, '2026-06-14T09:40:00'),
      act(3, '2026-06-14T11:15:00'),
    ])
    expect(activeHours).toEqual([11, 9]) // latest hour first
    expect(byHour.get(9)!.map((a) => a.id)).toEqual([2, 1]) // newest within hour first
    expect(byHour.get(11)!.map((a) => a.id)).toEqual([3])
    expect(railHours).toEqual([11, 10, 9]) // contiguous span hi→lo
  })

  it('returns empty structures when there is no activity', () => {
    const g = groupActivitiesByHour([])
    expect(g.activeHours).toEqual([])
    expect(g.railHours).toEqual([])
    expect(g.byHour.size).toBe(0)
  })
})
