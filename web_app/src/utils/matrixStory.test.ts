import { describe, expect, it } from 'vitest'
import {
  barsStory,
  adjacentScreens,
  chapterTitle,
  screenLabel,
  SCREENS,
  SECTION_EYEBROW,
  ratioPhrase,
  movesOf,
  type ChapterInput,
  CHAPTERS,
  columnsStory,
  compareStory,
  divergingStory,
  dotsStory,
  extremes,
  heatmapStory,
  lc,
  nameList,
  pivotStory,
  scatterStory,
  SECTION_ORDER,
  shareStory,
  tableStory,
  tilesStory,
  trendStory,
  type Item,
  type Story,
} from './matrixStory'

const pct1 = (v: number) => `${v.toFixed(1)}%`
const items = (o: Record<string, number | null>): Item[] => Object.entries(o).map(([name, value]) => ({ name, value }))
const BANNED = /\b(should|worrying|good|bad|best|worst|because|caused|will|expect|people|residents|crisis|improv)/i
const clean = (s: Story) => {
  expect(s.headline).not.toMatch(BANNED)
  if (s.lead) expect(s.lead).not.toMatch(BANNED)
}

describe('chapters', () => {
  it('has five chapters that cover each of the twelve sections once, in order', () => {
    expect(CHAPTERS.map((c) => c.id)).toEqual(['problem', 'decision', 'challenge', 'implementation', 'action'])
    expect(SECTION_ORDER).toEqual(['tiles', 'dots', 'share', 'dumbbell', 'diverging', 'bars', 'scatter', 'heatmap', 'trend', 'columns', 'pivot', 'table'])
    expect(new Set(SECTION_ORDER).size).toBe(12)
  })
})

describe('helpers', () => {
  it('lower-cases a label but keeps acronyms', () => {
    expect(lc('Poverty rate')).toBe('poverty rate')
    expect(lc('SNAP households')).toBe('SNAP households')
  })
  it('lists names, and counts a long list', () => {
    expect(nameList(['A'])).toBe('A')
    expect(nameList(['A', 'B'])).toBe('A and B')
    expect(nameList(['A', 'B', 'C'])).toBe('A, B and C')
    expect(nameList(['A', 'B', 'C', 'D'])).toBe('A, B, C and 1 other')
    expect(nameList(['A', 'B', 'C', 'D', 'E'])).toBe('A, B, C and 2 others')
  })
  it('names every geography that shares an extreme, and skips missing values', () => {
    const e = extremes(items({ B: 5, A: 5, C: 1, D: null }))
    expect(e.n).toBe(3)
    expect(e.high).toEqual({ names: ['A', 'B'], value: 5 })
    expect(e.low).toEqual({ names: ['C'], value: 1 })
    expect(e.median).toBe(5)
    expect(extremes([]).high).toBeNull()
  })
})

describe('tilesStory', () => {
  const base = { metricLabel: 'Poverty rate', vintage: '2023', fmt: pct1, lowerIsBetter: true }
  it('names the highest and gives the lowest and the median, factually, for a lower-is-better metric', () => {
    const s = tilesStory({ ...base, items: items({ Mississippi: 19.1, Utah: 8.6, Ohio: 13 }) })
    expect(s.headline).toBe('The middle sits at 13.0%, and 1 of 3 geographies are above it.')
    expect(s.lead).toBe('Mississippi is highest at 19.1%; Utah is lowest at 8.6%. Darker boxes are lower values.')
    clean(s)
  })
  it('does not mention shading direction for a higher-is-better metric', () => {
    const s = tilesStory({ ...base, lowerIsBetter: false, items: items({ A: 3, B: 1 }) })
    expect(s.lead).not.toMatch(/Darker/)
  })
  it('handles a tie, a single geography, all equal and missing data', () => {
    expect(tilesStory({ ...base, items: items({ A: 9, B: 9, C: 1 }) }).lead).toBe('A and B are highest at 9.0%; C is lowest at 1.0%. Darker boxes are lower values.')
    expect(tilesStory({ ...base, items: items({ A: 9, B: null }) })).toEqual({ headline: 'Only A has a value for poverty rate, 9.0%.', lead: null })
    expect(tilesStory({ ...base, items: items({ A: 9, B: 9 }) }).headline).toBe('All 2 geographies have the same poverty rate, 9.0%.')
    expect(tilesStory({ ...base, items: items({ A: null }) })).toEqual({ headline: 'Poverty rate, 2023: no tile values are available.', lead: null })
  })
})

describe('dotsStory', () => {
  const base = { metricLabel: 'Poverty rate', vintage: '2023', fmt: pct1 }
  it('reads the nation, and falls back to a neutral headline inside a state', () => {
    const s = dotsStory({ ...base, drillName: null, items: items({ A: 3, B: 1 }) })
    expect(s.headline).toBe('Where on the map? A is highest, at 3.0%.')
    expect(s.lead).toBe('B is lowest, at 1.0%. 2 states and territories have a value.')
    expect(dotsStory({ ...base, drillName: 'Alabama', items: [] })).toEqual({ headline: 'Poverty rate across Alabama counties, 2023.', lead: null })
  })
  it('handles single and missing', () => {
    expect(dotsStory({ ...base, drillName: null, items: items({ A: 3 }) }).lead).toBeNull()
    expect(dotsStory({ ...base, drillName: null, items: [] }).lead).toBeNull()
  })
})

describe('shareStory', () => {
  const base = { metricLabel: 'Population', vintage: '2023', whole: 'the U.S. total', unit: 'states' as const, hiddenCount: 0, partCount: 51 }
  it('names the largest share with the percentage the chart prints', () => {
    const s = shareStory({ ...base, segments: [{ name: 'California', value: 40, pct: 12 }, { name: 'Texas', value: 30, pct: 9 }] })
    expect(s.headline).toBe('California holds the largest share of the U.S. total, 12%.')
    expect(s.lead).toBe('Next is Texas, at 9%; 51 geographies in all.')
    clean(s)
  })
  it('handles ties, hidden segments, one segment and none', () => {
    expect(shareStory({ ...base, segments: [{ name: 'A', value: 5, pct: 50 }, { name: 'B', value: 5, pct: 50 }] }).headline).toBe('A and B tie for the largest share of the U.S. total, 50% each.')
    expect(shareStory({ ...base, hiddenCount: 1, segments: [{ name: 'A', value: 5, pct: 100 }] }).headline).toContain('the segments shown of the U.S. total')
    expect(shareStory({ ...base, partCount: 1, segments: [{ name: 'A', value: 5, pct: 100 }] }).lead).toBe('1 geography in all.')
    expect(shareStory({ ...base, unit: 'counties', partCount: 67, segments: [{ name: 'A', value: 5, pct: 100 }] }).lead).toBe('67 counties in all.')
    expect(shareStory({ ...base, segments: [] })).toEqual({ headline: 'Population, as a share of the U.S. total, 2023: no values are available.', lead: null })
  })
})

describe('compareStory', () => {
  const base = { metricLabel: 'Poverty rate', base: '2019', vintage: '2023', fmt: pct1, fmtChange: (a: number, b: number) => `${b - a > 0 ? '+' : ''}${(b - a).toFixed(1)} pp` }
  const pairs = [
    { name: 'A', from: 10, to: 12 },
    { name: 'B', from: 10, to: 9 },
    { name: 'C', from: 5, to: 6 },
    { name: 'D', from: null, to: 4 },
  ]
  it('counts the geographies that rose between the two years, as plain-string years', () => {
    const s = compareStory({ ...base, pairs })
    expect(s.headline).toBe('Which moved most? A, +2.0 pp, from 10.0% to 12.0%.')
    expect(s.lead).toBe('Between 2019 and 2023, 2 of 3 rose, 1 fell.')
    clean(s)
  })
  it('handles all up, all down, ties for the largest move, a single geography, no earlier vintage and no pairs', () => {
    expect(compareStory({ ...base, pairs: [{ name: 'A', from: 1, to: 2 }, { name: 'B', from: 1, to: 3 }] }).lead).toBe('Between 2019 and 2023, all 2 rose.')
    expect(compareStory({ ...base, pairs: [{ name: 'A', from: 2, to: 1 }, { name: 'B', from: 3, to: 1 }] }).lead).toBe('Between 2019 and 2023, all 2 fell.')
    expect(compareStory({ ...base, pairs: [{ name: 'A', from: 1, to: 2 }, { name: 'B', from: 1, to: 2 }, { name: 'C', from: 1, to: 1 }] }).headline).toBe('Which moved most? A and B, each by +1.0 pp.')
    expect(compareStory({ ...base, pairs: ['A', 'B', 'C', 'D'].map((name) => ({ name, from: 1, to: 2 })).concat([{ name: 'E', from: 2, to: 1 }]) }).headline).toBe('Which moved most? A, B, C and 1 other, each by +1.0 pp.')
    expect(compareStory({ ...base, pairs: [{ name: 'A', from: 1, to: 1 }, { name: 'B', from: 2, to: 2 }] }).headline).toBe('Since 2019, none of the 2 geographies changed.')
    expect(compareStory({ ...base, pairs: [{ name: 'A', from: 1, to: 2 }] })).toEqual({ headline: 'A went from 1.0% in 2019 to 2.0% in 2023.', lead: null })
    expect(compareStory({ ...base, base: '2023', pairs }).lead).toBeNull()
    expect(compareStory({ ...base, base: null, pairs }).headline).toBe('Poverty rate, 2023: there is no earlier year loaded to compare with.')
    expect(compareStory({ ...base, pairs: [{ name: 'A', from: null, to: 2 }] })).toEqual({ headline: 'Poverty rate, 2019 against 2023: no geography has both values.', lead: null })
  })
})

describe('divergingStory', () => {
  const base = { metricLabel: 'Poverty rate', vintage: '2023', fmt: pct1, fmtDiff: (hi: number, lo: number) => `${(hi - lo).toFixed(1)} pp` }
  it('counts the geographies above and below the median', () => {
    const s = divergingStory({ ...base, median: 10, items: items({ A: 14, B: 10, C: 7, D: 11, E: null }) })
    expect(s.headline).toBe('Who sits furthest from the middle? A is 4.0 pp above the median, C is 3.0 pp below.')
    expect(s.lead).toBe('2 of 4 sit above the median of 10.0% and 1 below; 1 equal it.')
    clean(s)
  })
  it('is neutral with fewer than three values or no median', () => {
    expect(divergingStory({ ...base, median: 1, items: items({ A: 1, B: 2 }) }).lead).toBeNull()
    expect(divergingStory({ ...base, median: null, items: items({ A: 1, B: 2, C: 3 }) }).headline).toContain('too few')
  })
})

describe('barsStory', () => {
  const base = { metricLabel: 'Poverty rate', vintage: '2023', scopeLabel: '52 states and territories', fmt: pct1 }
  it('gives the range with the geographies at both ends and the median', () => {
    const s = barsStory({ ...base, items: items({ A: 3, B: 9, C: 6 }) })
    expect(s.headline).toBe('Poverty rate runs from 3.0% in A to 9.0% in B.')
    expect(s.lead).toBe('Across 52 states and territories the median is 6.0%, from 3 geographies in 2023.')
    clean(s)
  })
  it('handles ties, a single geography, all equal and none', () => {
    expect(barsStory({ ...base, items: items({ A: 3, B: 9, C: 9 }) })).toEqual({ headline: 'Poverty rate runs from 3.0% to 9.0%.', lead: 'A is lowest and B and C are highest. Across 52 states and territories the median is 9.0%, from 3 geographies in 2023.' })
    expect(barsStory({ ...base, items: items({ A: 3 }) }).lead).toBeNull()
    expect(barsStory({ ...base, items: items({ A: 3, B: 3 }) }).lead).toBeNull()
    expect(barsStory({ ...base, items: [] }).headline).toContain('no bar values')
  })
})

describe('scatterStory', () => {
  const base = { xLabel: 'Median age', yLabel: 'Poverty rate', n: 52, total: 52 }
  it('states direction and how much of the spread a line accounts for, with r²', () => {
    const up = scatterStory({ ...base, fit: { slope: 0.4, r2: 0.32 } })
    expect(up.headline).toBe('Higher median age goes with higher poverty rate; a straight line accounts for 32% of the spread.')
    expect(up.lead).toBe('r² is 0.32; 52 of 52 geographies have both values.')
    expect(scatterStory({ ...base, fit: { slope: -2, r2: 0.7 } }).headline).toContain('Higher median age goes with lower poverty rate')
    expect(scatterStory({ ...base, fit: { slope: 0, r2: 0 } }).headline).toContain('no straight-line pattern')
    expect(scatterStory({ ...base, fit: { slope: 0.01, r2: 0.002 } }).headline).toContain('no straight-line pattern')
    clean(up)
  })
  it('is neutral without a fit or with fewer than three points', () => {
    expect(scatterStory({ ...base, fit: null }).lead).toBeNull()
    expect(scatterStory({ ...base, n: 2, fit: { slope: 1, r2: 1 } }).lead).toBeNull()
  })
})

describe('heatmapStory', () => {
  const base = { vintage: '2023', metricCount: 5, geoCount: 52 }
  it('names the geography with the darkest cell on the most metrics', () => {
    const s = heatmapStory({ ...base, leaders: [['Texas'], ['Texas'], ['Utah'], [], ['Texas']] })
    expect(s.headline).toBe('Who stands out? Texas has the darkest cell on 3 of 4 metrics.')
    expect(s.lead).toBe('5 metrics across 52 geographies, 2023; each column is ranked on its own.')
    clean(s)
  })
  it('handles ties, one apiece and no values', () => {
    expect(heatmapStory({ ...base, leaders: [['A'], ['B']] }).headline).toBe('No geography has the darkest cell on more than one of 2 metrics.')
    expect(heatmapStory({ ...base, leaders: [['A', 'B'], ['A', 'B']] }).headline).toBe('Who stands out? A and B each have the darkest cell on 2 of 2 metrics.')
    expect(heatmapStory({ ...base, leaders: [['A']] }).headline).toBe('Who stands out? A has the darkest cell on 1 of 1 metric.')
    expect(heatmapStory({ ...base, leaders: [[], []] }).lead).toBeNull()
  })
})

describe('trendStory', () => {
  const base = { metricLabel: 'Poverty rate', vintages: ['2019', '2021', '2023'], fmt: pct1 }
  it('reads the geographies drawn and the median at both ends', () => {
    const s = trendStory({ ...base, median: { first: 12, last: 13.5 }, geos: [{ name: 'A', first: 1, last: 2 }, { name: 'B', first: 2, last: 1 }, { name: 'C', first: 2, last: 2 }, { name: 'D', first: null, last: 2 }] })
    expect(s.headline).toBe('Of the 3 geographies drawn, 1 rose, 1 fell and 1 did not change from 2019 to 2023.')
    expect(s.lead).toBe('The median poverty rate went from 12.0% in 2019 to 13.5% in 2023.')
    clean(s)
  })
  it('handles an unchanged median, a single geography, one vintage, none and a missing end', () => {
    expect(trendStory({ ...base, median: { first: 5, last: 5 }, geos: [{ name: 'A', first: 1, last: 2 }] }).headline).toBe('The geography drawn rose from 2019 to 2023.')
    expect(trendStory({ ...base, median: { first: 5, last: 5 }, geos: [] })).toEqual({ headline: 'The median poverty rate held at 5.0% from 2019 to 2023.', lead: null })
    expect(trendStory({ ...base, vintages: ['2023'], median: { first: 5, last: 5 }, geos: [] }).headline).toBe('Poverty rate, 2023: this is the only year loaded, so there is no trend to draw yet.')
    expect(trendStory({ ...base, vintages: [], median: { first: null, last: null }, geos: [] }).headline).toBe('Poverty rate: no vintages are published.')
    expect(trendStory({ ...base, median: { first: null, last: 5 }, geos: [] }).lead).toBeNull()
  })
})

describe('columnsStory', () => {
  const regions = [{ label: 'South', value: 38 }, { label: 'West', value: 30 }, { label: 'Midwest', value: 20 }, { label: 'Northeast', value: 12 }]
  it('names the region with the largest share', () => {
    const s = columnsStory({ metricLabel: 'Population', isCount: true, vintage: '2023', regions })
    expect(s.headline).toBe('The South holds the largest share, 38.0%.')
    expect(s.lead).toBe('The West is next, at 30.0%, among the 4 regions shown in 2023.')
    clean(s)
  })
  it('handles ties, a non-count metric and missing values', () => {
    expect(columnsStory({ metricLabel: 'Population', isCount: true, vintage: '2023', regions: [{ label: 'South', value: 5 }, { label: 'West', value: 5 }] }).headline).toBe('The South and The West tie for the largest share, 50.0% each.')
    expect(columnsStory({ metricLabel: 'Poverty rate', isCount: false, vintage: '2023', regions }).lead).toBeNull()
    expect(columnsStory({ metricLabel: 'Population', isCount: true, vintage: null, regions: [] })).toEqual({ headline: 'Population by Census region: no values are available.', lead: null })
  })
})

describe('pivotStory', () => {
  const base = { vintage: '2023', colCount: 4, rowCount: 52, sortLabel: 'Poverty rate', fmt: pct1 }
  it('reads the end of the sorted column, either direction', () => {
    const d = pivotStory({ ...base, sortDir: 'desc', items: items({ A: 3, B: 9 }) })
    expect(d.headline).toBe('B is highest of 2 on poverty rate, at 9.0%.')
    expect(d.lead).toBe('4 metrics for 52 geographies, 2023; each column is shaded on its own scale.')
    expect(pivotStory({ ...base, sortDir: 'asc', items: items({ A: 3, B: 9 }) }).headline).toBe('A is lowest of 2 on poverty rate, at 3.0%.')
    clean(d)
  })
  it('handles ties, name sort, a single geography and no values', () => {
    expect(pivotStory({ ...base, sortDir: 'desc', items: items({ A: 9, B: 9 }) }).headline).toBe('A and B share the highest poverty rate, at 9.0%.')
    expect(pivotStory({ ...base, sortLabel: null, sortDir: 'asc', items: [] })).toEqual({ headline: '4 metrics for 52 geographies, 2023, sorted by name.', lead: null })
    expect(pivotStory({ ...base, sortDir: 'desc', items: items({ A: 9 }) }).headline).toBe('A is highest of 1 on poverty rate, at 9.0%.')
    expect(pivotStory({ ...base, sortDir: 'desc', items: [] }).lead).toBeNull()
  })
})

describe('tableStory', () => {
  const base = { vintage: '2023', base: '2019', total: 52, shown: 52, metricCount: 5, query: '', withChange: 51 }
  it('counts the rows and the rows with a change', () => {
    const s = tableStory(base)
    expect(s.headline).toBe('Every number, in one table: 52 geographies and 5 metrics, 2023.')
    expect(s.lead).toBe('51 of 52 rows have a change between 2019 and 2023.')
    clean(s)
  })
  it('handles a search, no match, one row, one vintage and no rows', () => {
    expect(tableStory({ ...base, query: 'ala', shown: 3 }).headline).toBe('Matching “ala”: 3 of 52 geographies.')
    expect(tableStory({ ...base, query: 'zzz', shown: 0 })).toEqual({ headline: 'No geography matches “zzz”.', lead: null })
    expect(tableStory({ ...base, total: 1, shown: 1, withChange: 1 }).headline).toBe('Every number, in one table: 1 geography and 5 metrics, 2023.')
    expect(tableStory({ ...base, base: '2023' }).lead).toBeNull()
    expect(tableStory({ ...base, total: 0, shown: 0 }).lead).toBeNull()
  })
})


// ---------- chapter titles (#883) ----------

const BANNED_WORDS = /\b(should|worrying|good|bad|best|worst|because|caused|driven by|due to|will|expect|people|residents|crisis|improv)/i
/** The structure of the page is never shown to the reader. */
const STRUCTURE = /\b(problem|challenge|implementation|call to action|call to order|new business|public comment|the motion|the vote and the work|decision)\b/i
const diff = (hi: number, lo: number) => `${(hi - lo).toFixed(1)} pp`
const chInput = (o: Partial<ChapterInput> = {}): ChapterInput => ({
  metricLabel: 'Poverty rate',
  vintage: '2023',
  vintages: ['2019', '2023'],
  fmt: pct1,
  fmtDiff: diff,
  fmtChange: (a, b) => `${b - a > 0 ? '+' : ''}${(b - a).toFixed(1)} pp`,
  items: items({ Washington: 22.5, Alabama: 3.5, 'Puerto Rico': 3.5, Montana: 12 }),
  baseItems: items({ Washington: 21, Alabama: 4, 'Puerto Rico': 3.5, Montana: 13 }),
  base: '2019',
  stateName: null,
  yLabel: 'Median age',
  fit: { slope: 0.4, r2: 0.32, n: 52 },
  medians: { first: 13, last: 12 },
  regions: null,
  ...o,
})
const cases: Record<string, ChapterInput> = {
  present: chInput(),
  missing: chInput({ items: [], baseItems: [], fit: null, medians: { first: null, last: null }, yLabel: null }),
  tie: chInput({ items: items({ A: 9, B: 9, C: 9, D: 9, E: 1, F: 1 }), baseItems: items({ A: 8, B: 8, C: 8, D: 8, E: 1, F: 0.5 }) }),
  single: chInput({ items: items({ Alabama: 9 }), baseItems: items({ Alabama: 8 }), fit: null }),
  oneVintage: chInput({ vintages: ['2023'], base: null, baseItems: null, medians: { first: 12, last: 12 } }),
  earliestSelected: chInput({ vintage: '2019', base: null, baseItems: null }),
  lowerIsBetter: chInput({ metricLabel: 'Uninsured rate', items: items({ A: 3, B: 14 }), baseItems: items({ A: 4, B: 15 }) }),
  state: chInput({ stateName: 'Alabama' }),
  noRelationship: chInput({ fit: { slope: 0, r2: 0, n: 52 } }),
  count: chInput({
    metricLabel: 'Population',
    regions: {
      first: { vintage: '2019', shares: [{ label: 'The South', value: 38 }, { label: 'The West', value: 30 }] },
      last: { vintage: '2023', shares: [{ label: 'The South', value: 40 }, { label: 'The West', value: 30 }] },
    },
  }),
}

describe('chapterTitle', () => {
  const ids = CHAPTERS.map((c) => c.id)
  it('writes one real sentence per chapter and case, with no structure words, judgments or leading numbers', () => {
    for (const [name, d] of Object.entries(cases)) {
      for (const id of ids) {
        const t = chapterTitle(id, d)
        expect(t.length, `${name}/${id}`).toBeGreaterThan(10)
        expect(t, `${name}/${id}`).not.toMatch(BANNED_WORDS)
        expect(t, `${name}/${id}`).not.toMatch(STRUCTURE)
        expect(t, `${name}/${id}`).not.toMatch(/^\d/)
        expect(t, `${name}/${id}`).not.toMatch(/(\d{4}) against \1/)
        expect(t.length, `${name}/${id}`).toBeLessThanOrEqual(150)
      }
    }
  })
  it('where things stand: the spread, as contrast with a gap', () => {
    expect(chapterTitle('problem', cases.present!)).toBe('Poverty rate: 22.5% in Washington. 3.5% in Alabama and Puerto Rico. That is 6.4 times as much.')
    expect(chapterTitle('problem', chInput({ items: items({ A: 10, B: 0 }) }))).toBe('Poverty rate: 10.0% in A. 0.0% in B. A gap of 10.0 pp.')
    expect(chapterTitle('problem', cases.single!)).toBe('Only Alabama has a value for poverty rate: 9.0%.')
    expect(chapterTitle('problem', chInput({ items: items({ A: 4, B: 4 }) }))).toBe('Every geography shows the same poverty rate: 4.0%.')
    expect(chapterTitle('problem', cases.missing!)).toBe('Poverty rate, 2023: no values are available for this scope.')
    expect(chapterTitle('problem', cases.tie!)).toContain('9.0% in A, B, C and 1 other.')
  })
  it('what changed: counts and the biggest mover, or who sits around the median with one year', () => {
    expect(chapterTitle('decision', cases.present!)).toBe('Since 2019, 1 of 4 rose and 2 fell. The biggest change was +1.5 pp.')
    expect(chapterTitle('decision', cases.oneVintage!)).toBe('Only 2023 is loaded. 2 of 4 geographies sit above the median of 7.8%, 2 below.')
    expect(chapterTitle('decision', cases.earliestSelected!)).toContain('The earliest year loaded is 2019.')
    expect(chapterTitle('decision', cases.missing!)).toContain('no geography has a value in both 2019 and 2023')
    expect(chapterTitle('decision', chInput({ baseItems: null }))).toBe('Poverty rate: the 2019 file is not available, so there is nothing to compare with.')
  })
  it('what goes with it: the relationship with direction and r², or plainly none', () => {
    expect(chapterTitle('challenge', cases.present!)).toBe('Do poverty rate and median age move together? Moderately: higher poverty rate goes with higher median age, r² 0.32 across 52 geographies.')
    expect(chapterTitle('challenge', cases.noRelationship!)).toBe('Do poverty rate and median age move together? Not in a straight line: r² is 0.00 across 52 geographies.')
    expect(chapterTitle('challenge', chInput({ fit: { slope: -1, r2: 0.7, n: 52 } }))).toContain('Strongly: higher poverty rate goes with lower median age')
    expect(chapterTitle('challenge', cases.missing!)).toBe('Poverty rate: no second metric is published to set beside it.')
    expect(chapterTitle('challenge', chInput({ fit: null }))).toContain('too few geographies')
  })
  it('over time: the median path, a region share for counts, or a single-year statement', () => {
    expect(chapterTitle('implementation', cases.present!)).toBe('From 2019 to 2023, the median poverty rate went from 13.0% to 12.0%.')
    expect(chapterTitle('implementation', chInput({ medians: { first: 5, last: 5 } }))).toBe('From 2019 to 2023, the median poverty rate held at 5.0%.')
    expect(chapterTitle('implementation', cases.oneVintage!)).toBe('Only 2023 is loaded, so there is no run of years yet. The median poverty rate is 12.0%.')
    expect(chapterTitle('implementation', cases.count!)).toBe('The South held the largest share of population in 2019 (55.9%) and in 2023 (57.1%).')
    expect(
      chapterTitle(
        'implementation',
        chInput({
          metricLabel: 'Population',
          regions: {
            first: { vintage: '2019', shares: [{ label: 'The West', value: 9 }, { label: 'The South', value: 5 }] },
            last: { vintage: '2023', shares: [{ label: 'The West', value: 5 }, { label: 'The South', value: 9 }] },
          },
        }),
      ),
    ).toBe('The West held the largest share of population in 2019 (64.3%). By 2023 it was The South (64.3%).')
    expect(chapterTitle('implementation', cases.missing!)).toContain('the median is not available at both ends')
  })
  it('your move: an invitation that names the scope', () => {
    expect(chapterTitle('action', cases.present!)).toBe('See the decisions behind these numbers.')
    expect(chapterTitle('action', cases.state!)).toBe('See what Alabama decided.')
  })
  it('never writes a ratio with a near-zero or non-positive smaller value', () => {
    expect(ratioPhrase(10, 0)).toBeNull()
    expect(ratioPhrase(10, -2)).toBeNull()
    expect(ratioPhrase(100, 3)).toBeNull()
    expect(ratioPhrase(10.2, 10)).toBeNull()
    expect(ratioPhrase(19.6, 10)).toBe('almost twice as much')
    expect(ratioPhrase(20, 10)).toBe('twice as much')
    expect(ratioPhrase(30, 10)).toBe('3 times as much')
  })
  it('finds who moved between two vintages by name', () => {
    expect(movesOf(items({ A: 3, B: null, C: 5 }), items({ A: 1, B: 2 }))).toEqual([{ name: 'A', from: 1, to: 3, d: 2 }])
  })
})

describe('every visible label and header', () => {
  const plain = { metricLabel: 'Poverty rate', base: '2019', yLabel: 'Median age', stateName: 'Alabama' }
  const labels = [
    ...CHAPTERS.map((c) => c.bandLabel),
    ...Object.values(SECTION_EYEBROW),
    ...SCREENS.map((s) => screenLabel(s.section, plain)),
    ...SCREENS.map((s) => screenLabel(s.section, { ...plain, base: null, yLabel: null, stateName: null })),
  ]
  it('uses no structure words, no judgments and never starts with a number', () => {
    expect(labels.length).toBeGreaterThan(30)
    for (const l of labels) {
      expect(l, l).not.toMatch(STRUCTURE)
      expect(l, l).not.toMatch(BANNED_WORDS)
      expect(l, l).not.toMatch(/^\s*\d/)
      expect(l.trim(), l).not.toBe('')
    }
  })
  it('never says "Matrix map" (the dot-matrix map chart is a different thing)', () => {
    for (const l of [...labels, 'Analysis']) expect(l, l).not.toMatch(/(?<![-\w])matrix map/i)
  })
  it('never frames the page as a story, chapters, a challenge or a game (census figures have no video or transcripts)', () => {
    const FRAMING = /\b(story|stories|chapters?|challenge|play|game)\b/i
    const sample = [...labels, ...Object.values(cases).flatMap((d) => CHAPTERS.map((c) => chapterTitle(c.id, d))), 'Analysis', 'Explore', 'Go further']
    for (const l of sample) expect(l, l).not.toMatch(FRAMING)
  })
  it('gives the five band labels in story order', () => {
    expect(CHAPTERS.map((c) => c.bandLabel)).toEqual(['Where things stand', 'What changed', 'What goes with it', 'Over time', 'Go further'])
  })
  it('keeps every section headline short enough for three lines in the left column and free of structure words', () => {
    const f = pct1
    const all: Story[] = [
      tilesStory({ metricLabel: 'Median household income', vintage: '2023', items: items({ 'District of Columbia': 102000, Mississippi: 52000, Utah: 80000 }), fmt: f, lowerIsBetter: false }),
      dotsStory({ metricLabel: 'Median household income', vintage: '2023', drillName: null, items: items({ A: 3, B: 1, C: 1, D: 1, E: 1 }), fmt: f }),
      compareStory({ metricLabel: 'Median household income', base: '2019', vintage: '2023', pairs: ['A', 'B', 'C', 'D', 'E'].map((name) => ({ name, from: 1, to: 2 })), fmt: f, fmtChange: () => '+1.0 pp' }),
      divergingStory({ metricLabel: 'Poverty rate', vintage: '2023', items: items({ A: 14, B: 10, C: 7, D: 11 }), median: 10.5, fmt: f, fmtDiff: diff }),
      barsStory({ metricLabel: 'Poverty rate', vintage: '2023', scopeLabel: '52 states and territories', items: items({ A: 3, B: 9, C: 9, D: 9, E: 9 }), fmt: f }),
      heatmapStory({ vintage: '2023', metricCount: 5, geoCount: 52, leaders: [['A', 'B', 'C', 'D'], ['A', 'B', 'C', 'D']] }),
      trendStory({ metricLabel: 'Poverty rate', vintages: ['2019', '2023'], median: { first: 1, last: 2 }, geos: [{ name: 'A', first: 1, last: 2 }, { name: 'B', first: 3, last: 2 }], fmt: f }),
      scatterStory({ xLabel: 'Median household income', yLabel: 'Poverty rate', n: 52, total: 52, fit: { slope: -1, r2: 0.4 } }),
      tableStory({ vintage: '2023', base: '2019', total: 52, shown: 52, metricCount: 5, query: '', withChange: 51 }),
    ]
    for (const s of all) {
      expect(s.headline.length, s.headline).toBeLessThanOrEqual(125)
      expect(s.headline, s.headline).not.toMatch(STRUCTURE)
      expect(s.headline, s.headline).not.toMatch(BANNED_WORDS)
      expect(s.headline, s.headline).not.toMatch(/^\d/)
      if (s.lead) expect(s.lead).not.toMatch(BANNED_WORDS)
    }
  })
})

describe('a tie reads the same in the headline and the lines after it', () => {
  it('names the same geographies in the lead of one section', () => {
    const t = tilesStory({ metricLabel: 'Poverty rate', vintage: '2023', items: items({ A: 9, B: 9, C: 1, D: 1 }), fmt: pct1, lowerIsBetter: false })
    expect(t.lead).toContain('A and B are highest')
    expect(t.lead).toContain('C and D are lowest')
  })
})

describe('paging between screens', () => {
  it('has thirteen screens: twelve sections, then the action block', () => {
    expect(SCREENS).toHaveLength(13)
    expect(SCREENS[0]!.domId).toBe('chapter-problem')
    expect(SCREENS[1]!.domId).toBe('dots')
    expect(SCREENS[12]!.domId).toBe('action')
  })
  it('has no previous screen at the first and no next at the last', () => {
    const first = adjacentScreens('chapter-problem')
    expect(first.prev).toBeNull()
    expect(first.next?.domId).toBe('dots')
    const last = adjacentScreens('action')
    expect(last.next).toBeNull()
    expect(last.prev?.domId).toBe('chapter-action')
  })
  it('crosses a chapter boundary: the next chapter opens on its opener', () => {
    const edge = adjacentScreens('share')
    expect(edge.prev?.domId).toBe('dots')
    expect(edge.next?.domId).toBe('chapter-decision')
    expect(adjacentScreens('chapter-decision').prev?.section).toBe('share')
    expect(adjacentScreens('bars').next?.domId).toBe('chapter-challenge')
  })
  it('treats a chapter first section and its opener as one screen', () => {
    expect(adjacentScreens('tiles').index).toBe(0)
    expect(adjacentScreens('dumbbell').next?.domId).toBe('diverging')
  })
  it('starts at the first screen from before it, or from an unknown id', () => {
    expect(adjacentScreens(null)).toEqual({ index: -1, prev: null, next: SCREENS[0] })
    expect(adjacentScreens('nowhere').next).toBe(SCREENS[0])
  })
  it('names the next screen in words that carry the scope', () => {
    const d = { metricLabel: 'Poverty rate', base: '2019', yLabel: 'Median age', stateName: null }
    expect(screenLabel('dumbbell', d)).toBe('what changed since 2019')
    expect(screenLabel('dumbbell', { ...d, base: null })).toBe('how the geographies compare')
    expect(screenLabel('scatter', d)).toBe('what goes with median age')
    expect(screenLabel('trend', d)).toBe('poverty rate over the years')
    expect(screenLabel('action', { ...d, stateName: 'Alabama' })).toBe('what Alabama decided')
  })
})
