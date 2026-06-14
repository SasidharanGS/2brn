import { describe, expect, it } from 'vitest'
import { buildPairingUrl } from '../pairing'

describe('buildPairingUrl', () => {
  it('encodes url and token into the twobrn deep link', () => {
    const u = buildPairingUrl('http://192.168.1.23:7842', 'tok EN/3')
    expect(u.startsWith('twobrn://pair?u=')).toBe(true)
    expect(u).toContain('u=http%3A%2F%2F192.168.1.23%3A7842')
    expect(u).toContain('t=tok%20EN%2F3')
  })

  it('round-trips back through URLSearchParams', () => {
    const url = 'http://10.0.0.5:7842'
    const token = 'a+b=c&d'
    const params = new URLSearchParams(buildPairingUrl(url, token).split('?')[1])
    expect(params.get('u')).toBe(url)
    expect(params.get('t')).toBe(token)
  })
})
