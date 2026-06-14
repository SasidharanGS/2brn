import { describe, expect, it } from 'vitest'
import { parseArgs, parseEnv } from '../pluginInput'

describe('parseArgs', () => {
  it('returns [] for blank text', () => {
    expect(parseArgs('')).toEqual([])
    expect(parseArgs('   \n  ')).toEqual([])
  })
  it('splits non-empty lines and trims each', () => {
    expect(parseArgs('--foo\n  --bar  \n\n--baz')).toEqual(['--foo', '--bar', '--baz'])
  })
})

describe('parseEnv', () => {
  it('parses KEY=value lines and trims around =', () => {
    expect(parseEnv('TOKEN=abc\nHOST = h')).toEqual({ TOKEN: 'abc', HOST: 'h' })
  })
  it('skips blank lines and # comments', () => {
    expect(parseEnv('# comment\n\nA=1')).toEqual({ A: '1' })
  })
  it('keeps = signs inside the value', () => {
    expect(parseEnv('URL=http://x?a=1&b=2')).toEqual({ URL: 'http://x?a=1&b=2' })
  })
  it('ignores lines with no key', () => {
    expect(parseEnv('=novalue\nGOOD=1')).toEqual({ GOOD: '1' })
  })
})
