import { describe, expect, it } from 'vitest'
import { rankShade, signedChange, statsOf } from './data'
import type { Metric, Row } from './types'

const metrics: Metric[] = [
  { slug: 'pov', label: 'Poverty rate', format: 'percent' },
  { slug: 'inc', label: 'Income', format: 'currency' },
]
const fmt = (_s: string, v: number | null) => (v == null ? '—' : String(v))
const row = (fips: string, v: number | null): Row => ({ fips, code: fips, name: fips, region: null, vals: { pov: v } })

describe('signedChange', () => {
  it('uses percentage points for percentage metrics and a signed number otherwise', () => {
    expect(signedChange('pov', 10, 23, metrics, fmt)).toBe('+13 pp')
    expect(signedChange('pov', 10, 8.5, metrics, fmt)).toBe('−1.5 pp')
    expect(signedChange('inc', 100, 70, metrics, fmt)).toBe('−30')
  })
  it('never computes a change from a missing value', () => {
    expect(signedChange('pov', null, 5, metrics, fmt)).toBe('—')
    expect(signedChange('pov', 5, undefined, metrics, fmt)).toBe('—')
  })
})

describe('rankShade', () => {
  it('shades the best rank 1 and the worst 0, flipping when lower is better', () => {
    const rows = [row('a', 1), row('b', 2), row('c', 3), row('d', null)]
    const hi = rankShade(rows, 'pov', false)
    expect([hi.get('a'), hi.get('b'), hi.get('c'), hi.get('d')]).toEqual([0, 0.5, 1, null])
    const lo = rankShade(rows, 'pov', true)
    expect([lo.get('a'), lo.get('c')]).toEqual([1, 0])
  })
})

describe('statsOf', () => {
  it('summarises only the geographies that have a value', () => {
    const s = statsOf([row('a', 1), row('b', 5), row('c', null)], 'pov')
    expect(s.n).toBe(2)
    expect(s.median).toBe(3)
    expect(s.high?.r.fips).toBe('b')
    expect(s.low?.r.fips).toBe('a')
    expect(statsOf([], 'pov').median).toBeNull()
  })
})
