// #1209: the Concerns dumbbell's rows — the place against the nation, or one share each nationally.
import { describe, expect, it } from 'vitest'
import { MIN_PLACE_MENTIONS, buildConcernRows, sortConcernRows } from './concernDumbbell'

type Row = [concern: string, mentions: number]
const rows = (xs: Row[]) => xs.map(([concern, mention_count]) => ({ concern, mention_count, objection_count: 5221, jurisdictions: [] }))
const NATIONAL = rows([
  ['traffic', 400],
  ['water', 300],
  ['land', 200],
  ['noise', 100],
])
const res = (items: Row[]) => ({ items: rows(items), national: NATIONAL }) as never

describe('buildConcernRows', () => {
  it('national scope: one share of mentions per concern, no comparison value', () => {
    const b = buildConcernRows(res([]), null)
    expect(b.mode).toBe('single')
    expect(b.nationalTotal).toBe(1000)
    expect(b.rows.map((r) => [r.key, r.place, r.national])).toEqual([
      ['traffic', 0.4, null],
      ['water', 0.3, null],
      ['land', 0.2, null],
      ['noise', 0.1, null],
    ])
    expect(b.hidden).toEqual([])
  })

  it('place scope: the place share against the national share, computed from mentions', () => {
    const b = buildConcernRows(res([['water', 6], ['traffic', 3], ['noise', 1]]), 'Texas')
    expect(b.mode).toBe('compare')
    expect(b.placeTotal).toBe(10)
    const water = b.rows.find((r) => r.key === 'water')!
    expect(water.place).toBeCloseTo(0.6)
    expect(water.national).toBeCloseTo(0.3)
    const traffic = b.rows.find((r) => r.key === 'traffic')!
    // A negative difference: Texas raises traffic less than the nation.
    expect(traffic.place - traffic.national!).toBeCloseTo(-0.1)
  })

  it('hides concerns under the threshold (zero included) but keeps them in the denominator', () => {
    const b = buildConcernRows(res([['water', 6], ['traffic', 3], ['noise', 1]]), 'Texas')
    expect(MIN_PLACE_MENTIONS).toBe(2)
    expect(b.rows.map((r) => r.key).sort()).toEqual(['traffic', 'water'])
    expect(b.hidden).toEqual(['noise', 'land and property'])
    expect(b.rows.find((r) => r.key === 'water')!.place).toBeCloseTo(0.6) // 6 of 10, not 6 of 9
  })

  it('a place with no national rows falls back to one value per concern', () => {
    const b = buildConcernRows({ items: rows([['water', 2]]), national: [] } as never, 'Texas')
    expect(b.mode).toBe('single')
    expect(b.rows[0]!.national).toBeNull()
  })

  it('no data is empty, never filled with national figures', () => {
    const b = buildConcernRows(res([]), 'Texas')
    expect(b.placeTotal).toBe(0)
    expect(b.rows).toEqual([])
    expect(buildConcernRows(null, null).rows).toEqual([])
  })
})

describe('sortConcernRows', () => {
  const b = buildConcernRows(res([['water', 6], ['traffic', 2], ['land', 2]]), 'Texas')
  it('by the place, by difference and nationally', () => {
    expect(sortConcernRows(b.rows, 'place').map((r) => r.key)).toEqual(['water', 'land', 'traffic'])
    expect(sortConcernRows(b.rows, 'difference').map((r) => r.key)).toEqual(['water', 'land', 'traffic'])
    expect(sortConcernRows(b.rows, 'national').map((r) => r.key)).toEqual(['traffic', 'water', 'land'])
  })
})
