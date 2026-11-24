import { describe, expect, it } from 'vitest'
import { MATRIX_TAB_LABEL, TRY_LIMIT, trySuggestions, tryYears } from './matrixSuggest'

const ms = (...slugs: string[]) => slugs.map((s) => ({ slug: s, label: s.toUpperCase() }))
const all = () => true

describe('trySuggestions', () => {
  it('lists the other metrics in the bundle order, without the current one', () => {
    expect(trySuggestions(ms('a', 'b', 'c'), 'b', all).map((m) => m.slug)).toEqual(['a', 'c'])
  })
  it('is stable: the same input gives the same order', () => {
    const m = ms('a', 'b', 'c', 'd')
    expect(trySuggestions(m, 'c', all)).toEqual(trySuggestions(m, 'c', all))
  })
  it('never suggests a metric that has no data', () => {
    expect(trySuggestions(ms('a', 'b', 'c'), 'a', (s) => s !== 'b').map((m) => m.slug)).toEqual(['c'])
  })
  it('caps the row and skips duplicates and blank labels', () => {
    const many = ms(...Array.from({ length: 20 }, (_, i) => `m${i}`))
    expect(trySuggestions(many, 'm0', all)).toHaveLength(TRY_LIMIT)
    expect(trySuggestions(many, 'm0', all, 3).map((m) => m.slug)).toEqual(['m1', 'm2', 'm3'])
    expect(trySuggestions([...ms('a'), ...ms('a'), { slug: 'z', label: ' ' }], 'q', all).map((m) => m.slug)).toEqual(['a'])
  })
  it('is empty when there is nothing else to try', () => {
    expect(trySuggestions(ms('a'), 'a', all)).toEqual([])
    expect(trySuggestions([], 'a', all)).toEqual([])
  })
})

describe('tryYears', () => {
  it('lists the other years, newest first, and nothing for one vintage', () => {
    expect(tryYears(['2019', '2021', '2023'], '2023')).toEqual(['2021', '2019'])
    expect(tryYears(['2023'], '2023')).toEqual([])
  })
})

describe('the tab label', () => {
  it('does not say "Matrix map"', () => {
    expect(MATRIX_TAB_LABEL).toBe('Analysis')
    expect(MATRIX_TAB_LABEL).not.toMatch(/matrix map/i)
  })
})
