import { describe, expect, it } from 'vitest'
import {
  barsStory,
  chapterLead,
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
    expect(nameList(['A', 'B', 'C', 'D'])).toBe('4 geographies')
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
    expect(s.headline).toBe('Mississippi sits highest on poverty rate, at 19.1%.')
    expect(s.lead).toBe('Lowest is Utah at 8.6%; the median is 13.0% across 3 geographies. Darker boxes are lower values.')
    clean(s)
  })
  it('does not mention shading direction for a higher-is-better metric', () => {
    const s = tilesStory({ ...base, lowerIsBetter: false, items: items({ A: 3, B: 1 }) })
    expect(s.lead).not.toMatch(/Darker/)
  })
  it('handles a tie, a single geography, all equal and missing data', () => {
    expect(tilesStory({ ...base, items: items({ A: 9, B: 9, C: 1 }) }).headline).toBe('A and B share the highest poverty rate, at 9.0%.')
    expect(tilesStory({ ...base, items: items({ A: 9, B: null }) })).toEqual({ headline: 'Only A has a value for poverty rate, 9.0%.', lead: null })
    expect(tilesStory({ ...base, items: items({ A: 9, B: 9 }) }).headline).toBe('All 2 geographies have the same poverty rate, 9.0%.')
    expect(tilesStory({ ...base, items: items({ A: null }) })).toEqual({ headline: 'Poverty rate, 2023: no tile values are available.', lead: null })
  })
})

describe('dotsStory', () => {
  const base = { metricLabel: 'Poverty rate', vintage: '2023', fmt: pct1 }
  it('reads the nation, and falls back to a neutral headline inside a state', () => {
    const s = dotsStory({ ...base, drillName: null, items: items({ A: 3, B: 1 }) })
    expect(s.headline).toBe('On the map, A shows the highest poverty rate, at 3.0%.')
    expect(s.lead).toBe('2 states and territories have a value; the lowest is B, at 1.0%.')
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
    expect(s.headline).toBe('2 of 3 geographies rose between 2019 and 2023.')
    expect(s.lead).toBe('1 fell; the largest move is A (+2.0 pp, from 10.0% to 12.0%).')
    clean(s)
  })
  it('handles all up, all down, ties for the largest move, a single geography, no earlier vintage and no pairs', () => {
    expect(compareStory({ ...base, pairs: [{ name: 'A', from: 1, to: 2 }, { name: 'B', from: 1, to: 3 }] }).headline).toBe('All 2 geographies rose between 2019 and 2023.')
    expect(compareStory({ ...base, pairs: [{ name: 'A', from: 2, to: 1 }, { name: 'B', from: 3, to: 1 }] }).headline).toBe('All 2 geographies fell between 2019 and 2023.')
    expect(compareStory({ ...base, pairs: [{ name: 'A', from: 1, to: 2 }, { name: 'B', from: 1, to: 2 }, { name: 'C', from: 1, to: 1 }] }).lead).toBe('1 did not change; the largest move, +1.0 pp, is shared by A and B.')
    expect(compareStory({ ...base, pairs: ['A', 'B', 'C', 'D'].map((name) => ({ name, from: 1, to: 2 })).concat([{ name: 'E', from: 2, to: 1 }]) }).lead).toBe('1 fell; the largest move, +1.0 pp, is shared by 4 geographies.')
    expect(compareStory({ ...base, pairs: [{ name: 'A', from: 1, to: 2 }] })).toEqual({ headline: 'A went from 1.0% in 2019 to 2.0% in 2023.', lead: null })
    expect(compareStory({ ...base, base: '2023', pairs }).lead).toBeNull()
    expect(compareStory({ ...base, base: null, pairs }).headline).toBe('Poverty rate, 2023: there is no earlier vintage to compare with.')
    expect(compareStory({ ...base, pairs: [{ name: 'A', from: null, to: 2 }] })).toEqual({ headline: 'Poverty rate, 2019 against 2023: no geography has both values.', lead: null })
  })
})

describe('divergingStory', () => {
  const base = { metricLabel: 'Poverty rate', vintage: '2023', fmt: pct1 }
  it('counts the geographies above and below the median', () => {
    const s = divergingStory({ ...base, median: 10, items: items({ A: 14, B: 10, C: 7, D: 11, E: null }) })
    expect(s.headline).toBe('2 of 4 geographies sit above the median of 10.0%.')
    expect(s.lead).toBe('1 sit below it and 1 equal it; the widest gap is A, at 14.0%.')
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
    expect(s.headline).toBe('Across 52 states and territories, poverty rate runs from 3.0% (A) to 9.0% (B).')
    expect(s.lead).toBe('The median is 6.0% across 3 geographies in 2023.')
    clean(s)
  })
  it('handles ties, a single geography, all equal and none', () => {
    expect(barsStory({ ...base, items: items({ A: 3, B: 9, C: 9 }) }).headline).toContain('9.0% (B and C)')
    expect(barsStory({ ...base, items: items({ A: 3 }) }).lead).toBeNull()
    expect(barsStory({ ...base, items: items({ A: 3, B: 3 }) }).lead).toBeNull()
    expect(barsStory({ ...base, items: [] }).headline).toContain('no bar values')
  })
})

describe('scatterStory', () => {
  const base = { xLabel: 'Median age', yLabel: 'Poverty rate', n: 52, total: 52 }
  it('states direction and strength with r²', () => {
    const up = scatterStory({ ...base, fit: { slope: 0.4, r2: 0.32 } })
    expect(up.headline).toBe('Poverty rate rises with median age, moderately; r² is 0.32 across 52 geographies.')
    expect(up.lead).toBe('r² is the share of the spread in poverty rate that a straight line on median age accounts for; 52 of 52 geographies have both values.')
    expect(scatterStory({ ...base, fit: { slope: -2, r2: 0.7 } }).headline).toBe('Poverty rate falls as median age rises, strongly; r² is 0.70 across 52 geographies.')
    expect(scatterStory({ ...base, fit: { slope: 0.1, r2: 0.04 } }).headline).toContain('very weakly')
    expect(scatterStory({ ...base, fit: { slope: 0, r2: 0 } }).headline).toContain('no straight-line relationship')
    expect(scatterStory({ ...base, fit: { slope: 0.01, r2: 0.002 } }).headline).toContain('no straight-line relationship')
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
    expect(s.headline).toBe('Texas has the darkest cell on 3 of 4 metrics.')
    expect(s.lead).toBe('5 metrics across 52 geographies, 2023; each column is ranked on its own.')
    clean(s)
  })
  it('handles ties, one apiece and no values', () => {
    expect(heatmapStory({ ...base, leaders: [['A'], ['B']] }).headline).toBe('No geography has the darkest cell on more than one of 2 metrics.')
    expect(heatmapStory({ ...base, leaders: [['A', 'B'], ['A', 'B']] }).headline).toBe('A and B each have the darkest cell on 2 of 2 metrics.')
    expect(heatmapStory({ ...base, leaders: [['A']] }).headline).toBe('A has the darkest cell on 1 of 1 metric.')
    expect(heatmapStory({ ...base, leaders: [[], []] }).lead).toBeNull()
  })
})

describe('trendStory', () => {
  const base = { metricLabel: 'Poverty rate', vintages: ['2019', '2021', '2023'], fmt: pct1 }
  it('reads the median at both ends and the geographies drawn', () => {
    const s = trendStory({ ...base, median: { first: 12, last: 13.5 }, geos: [{ name: 'A', first: 1, last: 2 }, { name: 'B', first: 2, last: 1 }, { name: 'C', first: 2, last: 2 }, { name: 'D', first: null, last: 2 }] })
    expect(s.headline).toBe('The median poverty rate went from 12.0% in 2019 to 13.5% in 2023.')
    expect(s.lead).toBe('Of the 3 geographies drawn, 1 rose, 1 fell, 1 did not change over the same years.')
    clean(s)
  })
  it('handles an unchanged median, a single geography, one vintage, none and a missing end', () => {
    expect(trendStory({ ...base, median: { first: 5, last: 5 }, geos: [{ name: 'A', first: 1, last: 2 }] }).lead).toBe('The geography drawn rose over the same years.')
    expect(trendStory({ ...base, median: { first: 5, last: 5 }, geos: [] })).toEqual({ headline: 'The median poverty rate stayed at 5.0% from 2019 to 2023.', lead: null })
    expect(trendStory({ ...base, vintages: ['2023'], median: { first: 5, last: 5 }, geos: [] }).headline).toBe('Poverty rate, 2023: only one vintage is published, so there is no trend to draw.')
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
    expect(s.headline).toBe('52 geographies, 5 metrics, 2023.')
    expect(s.lead).toBe('51 of 52 rows have a change between 2019 and 2023.')
    clean(s)
  })
  it('handles a search, no match, one row, one vintage and no rows', () => {
    expect(tableStory({ ...base, query: 'ala', shown: 3 }).headline).toBe('3 of 52 geographies match “ala”.')
    expect(tableStory({ ...base, query: 'zzz', shown: 0 })).toEqual({ headline: 'No geography matches “zzz”.', lead: null })
    expect(tableStory({ ...base, total: 1, shown: 1, withChange: 1 }).headline).toBe('1 geography, 5 metrics, 2023.')
    expect(tableStory({ ...base, base: '2023' }).lead).toBeNull()
    expect(tableStory({ ...base, total: 0, shown: 0 }).lead).toBeNull()
  })
})

describe('chapterLead', () => {
  const d = { metricLabel: 'Poverty rate', vintage: '2023', vintages: ['2019', '2023'], geoNoun: '52 states and territories', yLabel: 'Median age', stateName: null }
  it('writes one sentence per chapter from the scope', () => {
    expect(chapterLead('problem', d)).toBe('Poverty rate, 2023 ACS 5-year: where things stand across 52 states and territories.')
    expect(chapterLead('decision', d)).toContain('between 2019 and 2023')
    expect(chapterLead('challenge', d)).toBe('Poverty rate set beside median age, and beside every metric at once, for 52 states and territories.')
    expect(chapterLead('implementation', d)).toBe('Poverty rate across 2 vintages, 2019 to 2023.')
    expect(chapterLead('action', d)).toContain('all states and territories')
    expect(chapterLead('action', { ...d, stateName: 'Alabama' })).toContain('Alabama')
  })
  it('says so when there is one vintage, no geography or no second metric', () => {
    expect(chapterLead('decision', { ...d, vintages: ['2023'] })).toContain('no earlier vintage')
    expect(chapterLead('implementation', { ...d, vintages: ['2023'] })).toBe('Poverty rate: only 2023 is published, so there is no run of years to show.')
    expect(chapterLead('problem', { ...d, geoNoun: null })).toContain('no geography has data')
    expect(chapterLead('challenge', { ...d, yLabel: null, geoNoun: null })).toBe('Poverty rate set beside the other published metrics, and beside every metric at once.')
  })
})
