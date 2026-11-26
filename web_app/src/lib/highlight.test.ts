import { describe, expect, it } from 'vitest'
import { excerptAroundMark } from './highlight'

describe('excerptAroundMark (#995)', () => {
  it('keeps a short passage whole', () => {
    expect(excerptAroundMark('We do not need another <mark>data center</mark> here.')).toBe('We do not need another <mark>data center</mark> here.')
  })
  it('cuts a long passage around the first match, at word edges, keeping the mark whole', () => {
    const long = `${'word '.repeat(80)}we discussed the <mark>data center</mark> rezoning ${'more '.repeat(80)}`
    const out = excerptAroundMark(long, 120)
    expect(out.startsWith('… ')).toBe(true)
    expect(out.endsWith(' …')).toBe(true)
    expect(out).toContain('<mark>data center</mark>')
    expect((out.match(/<mark>/g) ?? []).length).toBe((out.match(/<\/mark>/g) ?? []).length)
    expect(out.replace(/<\/?mark>/g, '').length).toBeLessThan(200)
  })
})
