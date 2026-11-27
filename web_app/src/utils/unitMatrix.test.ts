import { describe, expect, it } from 'vitest'
import {
  availableGroupings,
  groupLabel,
  groupRecords,
  layoutMatrix,
  MAX_PLACE_GROUPS,
  outcomeFromDc,
  outcomeFromText,
  sideFromLean,
  type MatrixRecord,
} from './unitMatrix'

const rec = (facets: MatrixRecord['facets'], nativeKey?: string): MatrixRecord => ({ facets, nativeKey })

describe('groupings offered', () => {
  it('offers a grouping only when the records carry its field', () => {
    const rs = [rec({ year: '2026', state: 'TX' }), rec({ year: '2025', state: 'TX' })]
    expect(availableGroupings(rs, false, 'state')).toEqual(['all', 'year', 'place'])
    expect(availableGroupings(rs, false, 'town')).toEqual(['all', 'year'])
    expect(availableGroupings([rec({ outcome: 'approved', side: 'against' })], true, 'state')).toEqual(['all', 'native', 'outcome', 'side'])
  })
})

describe('groupRecords', () => {
  const rs = [
    rec({ year: '2026', outcome: 'approved', side: 'against' }, 'a'),
    rec({ year: '2026', outcome: 'denied' }, 'a'),
    rec({ year: '2025', outcome: 'approved', side: 'no_side' }, 'b'),
    rec({ year: null }, 'b'),
  ]

  it('All is one block at 100%', () => {
    const g = groupRecords(rs, 'all')
    expect(g).toHaveLength(1)
    expect(g[0]).toMatchObject({ count: 4, pct: 100 })
  })

  it('groups by year newest first, with undated records last, and percentages from the counts', () => {
    const g = groupRecords(rs, 'year')
    expect(g.map((x) => [x.label, x.count, x.pct])).toEqual([
      ['2026', 2, 50],
      ['2025', 1, 25],
      ['Date not given', 1, 25],
    ])
    expect(g.reduce((a, x) => a + x.count, 0)).toBe(rs.length)
  })

  it('groups outcomes in a fixed order and never draws a zero group', () => {
    const g = groupRecords(rs, 'outcome')
    expect(g.map((x) => x.label)).toEqual(['Approved', 'Denied', 'Not screened'])
    expect(g.every((x) => x.count > 0)).toBe(true)
    expect(g[0]!.tone).toBe('approved')
    expect(groupRecords(rs, 'side').map((x) => [x.label, x.count])).toEqual([
      ['Public mostly opposed', 1],
      ['No side taken', 1],
      ['Not screened', 2],
    ])
  })

  it('keeps the chart’s own groups in their order', () => {
    const g = groupRecords(rs, 'native', { native: [{ key: 'b', label: 'Without debate' }, { key: 'a', label: 'Debated' }, { key: 'z', label: 'Empty' }] })
    expect(g.map((x) => [x.label, x.count])).toEqual([
      ['Without debate', 2],
      ['Debated', 2],
    ])
  })

  it('folds places past the cap into one real "Other places" count', () => {
    const many = Array.from({ length: 12 }, (_, i) => rec({ state: `S${String(i).padStart(2, '0')}` }))
    many.push(rec({ state: 'S00' }))
    const g = groupRecords(many, 'place', { placeGrain: 'state', placeLabel: (k) => `State ${k}` })
    expect(g).toHaveLength(MAX_PLACE_GROUPS + 1)
    expect(g[0]).toMatchObject({ label: 'State S00', count: 2 })
    expect(g[g.length - 1]).toMatchObject({ key: 'other', label: 'Other places (4)', count: 4 })
    expect(g.reduce((a, x) => a + x.count, 0)).toBe(13)
  })

  it('labels a block "Name · N (x%)"', () => {
    expect(groupLabel({ label: 'Approved', count: 1234, pct: 40 })).toBe('Approved · 1,234 (40.0%)')
  })
})

describe('layoutMatrix', () => {
  it('gives every record a square and keeps record i at index i across groupings', () => {
    const rs = [rec({ year: '2026' }), rec({ year: '2025' }), rec({ year: '2026' })]
    const all = layoutMatrix(3, groupRecords(rs, 'all'), 600, 'all')
    const by = layoutMatrix(3, groupRecords(rs, 'year'), 600, 'year')
    expect(all.squares).toHaveLength(3)
    expect(by.squares).toHaveLength(3)
    // record 2 (2026) moves next to record 0 in the 2026 block
    expect(by.squares[2]!.y).toBe(by.squares[0]!.y)
    expect(by.labels.map((l) => l.text)).toEqual(['2026 · 2 (66.7%)', '2025 · 1 (33.3%)'])
  })
})

describe('field readers', () => {
  it('maps the AI readings and recorded outcome text', () => {
    expect(outcomeFromDc('tabled_or_deferred')).toBe('tabled')
    expect(outcomeFromDc('no_data_center_item')).toBeNull()
    expect(outcomeFromText('Approved with conditions')).toBe('approved')
    expect(outcomeFromText('Deferred')).toBe('tabled')
    expect(outcomeFromText('Discussion')).toBe('no_action')
    expect(outcomeFromText('')).toBeNull()
    expect(sideFromLean('mostly_opposed')).toBe('against')
    expect(sideFromLean(null)).toBeNull()
  })
})

describe('side labels in topic words (#1200)', () => {
  it('names the "By who spoke" groups with the topic position words', async () => {
    const { groupRecords, sideLabelsFor } = await import('./unitMatrix')
    const { topicPositions } = await import('./topicPositions')
    const recs = [{ facets: { side: 'against' as const } }, { facets: { side: 'no_side' as const } }]
    const g = groupRecords(recs, 'side', { sideLabels: sideLabelsFor(topicPositions('data-centers')) })
    expect(g.map((x) => x.label)).toEqual(['Against data centers', "Public didn't speak on it"])
  })
})
