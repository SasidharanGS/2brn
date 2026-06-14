import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ActivityRecord } from '../api/types'
import { groupActivitiesByHour } from '../utils/timeline'

/**
 * The Timeline's hour-rail interaction — extracted so both skins share ONE copy
 * (it used to be duplicated byte-for-byte across the two screens: the scroll-spy
 * effect, the nearest-active-hour `goToHour`, and the section refs). Presentation
 * stays per-skin; this owns all the behaviour.
 */
export function useHourScroll(filtered: ActivityRecord[]) {
  const [activeHour, setActiveHour] = useState<number | null>(null)
  const [hoverHour, setHoverHour] = useState<number | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const hourRefs = useRef<Record<number, HTMLElement | null>>({})

  const { byHour, activeHours, railHours } = useMemo(() => groupActivitiesByHour(filtered), [filtered])

  const setHourRef = useCallback((h: number, el: HTMLElement | null) => {
    hourRefs.current[h] = el
  }, [])

  const goToHour = useCallback((h: number) => {
    let target = h
    if (!byHour.has(h) && activeHours.length) {
      // nearest active hour by absolute distance (order-independent)
      target = activeHours.reduce((best, cur) => (Math.abs(cur - h) < Math.abs(best - h) ? cur : best), activeHours[0])
    }
    const el = hourRefs.current[target]
    const sc = scrollRef.current
    // Scroll the feed container by offset — never scrollIntoView (it shifts the
    // whole app layout).
    if (el && sc) sc.scrollTo({ top: el.offsetTop - 8, behavior: 'smooth' })
    setActiveHour(target)
  }, [byHour, activeHours])

  // Scroll-spy: highlight the hour group whose heading is at the top of the feed —
  // the bottom-most section whose top has scrolled past (max offsetTop ≤ scrollTop),
  // independent of activeHours ordering.
  useEffect(() => {
    const sc = scrollRef.current
    if (!sc) return
    const onScroll = () => {
      let cur: number | null = activeHours[0] ?? null
      let bestTop = -Infinity
      for (const h of activeHours) {
        const el = hourRefs.current[h]
        if (el && el.offsetTop - 20 <= sc.scrollTop && el.offsetTop > bestTop) {
          bestTop = el.offsetTop
          cur = h
        }
      }
      setActiveHour(cur)
    }
    onScroll()
    sc.addEventListener('scroll', onScroll, { passive: true })
    return () => sc.removeEventListener('scroll', onScroll)
  }, [filtered]) // eslint-disable-line react-hooks/exhaustive-deps

  return {
    byHour, activeHours, railHours,
    activeHour, hoverHour, setHoverHour,
    goToHour, scrollRef, setHourRef,
  }
}
