import { describe, expect, it } from 'vitest'
import { deltaPct, fmtPct } from '../useInsightsData'

describe('deltaPct', () => {
  it('is null when the baseline is empty but there is current activity', () => {
    expect(deltaPct(5, 0)).toBeNull()
  })
  it('is 0 when both are zero', () => {
    expect(deltaPct(0, 0)).toBe(0)
  })
  it('rounds the relative change to whole percent', () => {
    expect(deltaPct(12, 10)).toBe(20)
    expect(deltaPct(8, 10)).toBe(-20)
  })
})

describe('fmtPct', () => {
  it('formats to one decimal place with a percent sign', () => {
    expect(fmtPct(12.34)).toBe('12.3%')
  })
})
