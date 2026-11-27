import { describe, expect, it } from 'vitest'
import { countsSentence, pickDisplay, topCategories } from './displayFit'

// One test per row of the rule table (#1289, web_docs/docs/development/story-display-fit.md).
describe('pickDisplay: the display fits the count (#1289)', () => {
  it('row 1: 0 items is the empty state, never a row of zeros', () => {
    expect(pickDisplay({ items: 0 }).kind).toBe('empty')
    expect(pickDisplay({ items: 0, categories: [0, 0, 0] }).kind).toBe('empty')
  })

  it('row 2: 1 to 5 items is a sentence and a list, whatever the categories', () => {
    for (const n of [1, 2, 3, 4, 5]) expect(pickDisplay({ items: n }).kind).toBe('list')
    // The Alabama proposals: 3 projects in 2 statuses are a list, not 3 squares with a legend.
    expect(pickDisplay({ items: 3, categories: [2, 1] }).kind).toBe('list')
    expect(pickDisplay({ items: 6, categories: [4, 2] }).kind).not.toBe('list')
  })

  it('row 3: 2 to 7 categories with a total under 20 is the numbers in a sentence', () => {
    expect(pickDisplay({ items: 10, categories: [8, 2] }).kind).toBe('sentence')
    expect(pickDisplay({ items: 19, categories: [5, 4, 3, 3, 2, 1, 1] }).kind).toBe('sentence')
  })

  it('row 4: 2 to 7 categories with a total of 20 or more is sorted bars labelled with counts', () => {
    expect(pickDisplay({ items: 20, categories: [10, 10] }).kind).toBe('bars')
    expect(pickDisplay({ items: 29, categories: [11, 4, 13, 1] }).kind).toBe('bars')
    expect(pickDisplay({ items: 172, categories: [76, 33, 29, 19, 9, 5, 1] }).kind).toBe('bars')
  })

  it('row 5: 8 or more categories is the top 7 plus "Other"', () => {
    const d = pickDisplay({ items: 197, categories: [159, 14, 5, 4, 3, 3, 3, 2, 2, 1, 1] })
    expect(d.kind).toBe('top-bars')
    const rows = topCategories([
      ...['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i'].map((label, i) => ({ label, count: 9 - i })),
    ])
    expect(rows).toHaveLength(8)
    expect(rows.slice(0, 7).map((r) => r.label)).toEqual(['a', 'b', 'c', 'd', 'e', 'f', 'g'])
    expect(rows[7]).toEqual({ label: 'Other', count: 2 + 1, other: true })
  })

  it('row 6: a time series is a line only with 6 or more points', () => {
    expect(pickDisplay({ items: 80, seriesPoints: 6 }).kind).toBe('line')
    expect(pickDisplay({ items: 80, seriesPoints: 5 }).kind).toBe('sentence')
    expect(pickDisplay({ items: 3, seriesPoints: 2 }).kind).toBe('list')
    expect(pickDisplay({ items: 0, seriesPoints: 0 }).kind).toBe('empty')
  })

  it('row 7: dot or unit charts only for about 20 to 200 individual items', () => {
    expect(pickDisplay({ items: 20, categories: [20] }).kind).toBe('units')
    expect(pickDisplay({ items: 200, categories: [200] }).kind).toBe('units')
    expect(pickDisplay({ items: 19, categories: [19] }).kind).toBe('list')
    expect(pickDisplay({ items: 201, categories: [201] }).kind).toBe('sentence')
    // Never units with several categories: that row is bars.
    for (const n of [20, 50, 200]) expect(pickDisplay({ items: n, categories: [n - 5, 5] }).kind).toBe('bars')
  })

  it('the sentence states counts, larger first, with no percentages', () => {
    const s = countsSentence([
      { label: 'Without debate', count: 2 },
      { label: 'Debated', count: 8 },
    ])
    expect(s).toBe('Debated: 8; without debate: 2.')
    expect(s).not.toMatch(/%/)
  })
})
