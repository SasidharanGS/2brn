import { describe, expect, it } from 'vitest'
import { fmtDur } from '../time'

describe('fmtDur', () => {
  it('shows <1m for sub-minute durations', () => {
    expect(fmtDur(20)).toBe('<1m')
    expect(fmtDur(0)).toBe('<1m')
  })
  it('rounds to the nearest minute', () => {
    expect(fmtDur(89)).toBe('1m') // 1.48m → 1
    expect(fmtDur(45 * 60)).toBe('45m')
  })
  it('shows whole hours without trailing minutes', () => {
    expect(fmtDur(3 * 3600)).toBe('3h')
  })
  it('shows hours and minutes together', () => {
    expect(fmtDur(3 * 3600 + 12 * 60)).toBe('3h 12m')
  })
})
