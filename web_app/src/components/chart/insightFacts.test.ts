import { describe, expect, it } from 'vitest'
import { toConcern, toHeatByYear } from './insightFacts'
import { pickInsight } from '../../utils/chartInsight'

// Test-only fixtures: nothing here is served by the app.
describe('insight facts mapping (#1418)', () => {
  it('maps heat rows to the picker shape and drops an empty answer', () => {
    expect(toHeatByYear({ topic: 't', years: [{ year: '2026', mean: 2.9, speakers_rated: 55, share_heated: 0.4, speakers_heated: 22 }] })).toEqual([
      { year: '2026', mean: 2.9, rated: 55 },
    ])
    expect(toHeatByYear({ topic: 't', years: [] })).toBeUndefined()
    expect(toHeatByYear(undefined)).toBeUndefined()
  })
  it('needs a label, counts and a basis for a concern', () => {
    expect(toConcern({ topic: 't', label: 'Water use', count: 31, of: 80, basis: 'opposing', share: 0.39 })).toEqual({
      label: 'water use', count: 31, of: 80, basis: 'opposing',
    })
    expect(toConcern({ topic: 't', label: null, count: null, of: null, basis: null, share: null })).toBeUndefined()
    expect(toConcern({ topic: 't', label: 'Noise', count: 5, of: 0, basis: 'heated', share: null })).toBeUndefined()
  })
  it('fires heat only when the picker thresholds are met', () => {
    const base = { subject: 'data centers', place: 'Virginia' }
    const rows = (a: number, b: number) =>
      toHeatByYear({ topic: 't', years: [
        { year: '2025', mean: 1.4, speakers_rated: a, share_heated: null, speakers_heated: null },
        { year: '2026', mean: 2.9, speakers_rated: b, share_heated: null, speakers_heated: null },
      ] })
    expect(pickInsight({ ...base, heatByYear: rows(40, 55) }).kind).toBe('heat')
    expect(pickInsight({ ...base, heatByYear: rows(10, 55) }).kind).not.toBe('heat')
  })
  it('names the top concern only with a clear against lean and enough turns', () => {
    const lean = { unit: 'speakers' as const, against: 60, for: 10, other: 10 }
    const concern = toConcern({ topic: 't', label: 'Water use', count: 31, of: 80, basis: 'opposing', share: 0.39 })
    expect(pickInsight({ subject: 'data centers', place: 'Virginia', lean, concern }).title).toContain('water use leads the complaints')
    const weak = toConcern({ topic: 't', label: 'Water use', count: 4, of: 80, basis: 'opposing', share: 0.05 })
    expect(pickInsight({ subject: 'data centers', place: 'Virginia', lean, concern: weak }).title).not.toContain('leads the complaints')
  })
})
