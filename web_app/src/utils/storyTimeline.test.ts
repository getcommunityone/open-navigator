import { describe, expect, it } from 'vitest'
import type { PeriodRow, TimelineMilestone, TimelineYear } from '../api/topicTimeline'
import {
  buildSeries,
  dateToYearPos,
  defaultMarker,
  gapYears,
  defaultSeriesMode,
  isHollow,
  splitRun,
  thinNote,
  thinYears,
  milestoneLanes,
  niceMax,
  ppLabel,
  seriesValue,
  sortDumbbell,
  stepMarker,
} from './storyTimeline'

const yr = (year: string, meetings: number, rec: number | null, passages: number | null = null): TimelineYear => ({
  year,
  meetings,
  passages,
  all_recorded_meetings: rec,
  share: rec ? meetings / rec : null,
})

describe('buildSeries', () => {
  it('breaks the line at a missing year instead of bridging it', () => {
    const runs = buildSeries([yr('2021', 3, 485), yr('2022', 1, 450), yr('2025', 4, 271), yr('2026', 38, 509)], 'meetings')
    expect(runs.map((r) => r.map((p) => p.year))).toEqual([[2021, 2022], [2025, 2026]])
  })

  it('draws a real zero only when enough meetings were recorded; otherwise the year is a gap', () => {
    // Texas 2024: 7 recorded meetings, none about the topic → gap. 2023: 243 recorded, none → a real 0.
    expect(seriesValue(yr('2024', 0, 7), 'meetings')).toBeNull()
    expect(seriesValue(yr('2023', 0, 243), 'meetings')).toBe(0)
    const runs = buildSeries([yr('2023', 4, 243), yr('2024', 0, 7), yr('2025', 4, 271)], 'meetings')
    expect(runs).toHaveLength(2)
    expect(gapYears([yr('2023', 4, 243), yr('2024', 0, 7), yr('2025', 4, 271)], 'meetings')).toEqual(['2024'])
  })

  it('plots the share as a percentage and leaves out years with no denominator', () => {
    const runs = buildSeries([yr('2025', 4, 271), yr('2026', 38, 509), yr('2027', 2, null)], 'share')
    expect(runs).toHaveLength(1)
    expect(runs[0]!.map((p) => Math.round(p.value * 10) / 10)).toEqual([1.5, 7.5])
  })

  it('sorts unsorted years and ignores non-numeric ones', () => {
    const runs = buildSeries([yr('2026', 2, 100), yr('x', 1, 10), yr('2025', 1, 100)], 'meetings')
    expect(runs[0]!.map((p) => p.year)).toEqual([2025, 2026])
  })
})

describe('marker selection', () => {
  const ms = (n: number): TimelineMilestone[] =>
    Array.from({ length: n }, (_, i) => ({ date: `2026-0${(i % 9) + 1}-01`, kind: 'approved', place: null, state_code: null, title: null, url: null, source: 'ai_reading' }))

  it('starts on the newest milestone, or none', () => {
    expect(defaultMarker(ms(3))).toBe(2)
    expect(defaultMarker([])).toBe(-1)
  })

  it('moves with the arrow keys, clamped at the ends, and jumps with Home/End', () => {
    expect(stepMarker(1, 'ArrowRight', 3)).toBe(2)
    expect(stepMarker(2, 'ArrowRight', 3)).toBe(2)
    expect(stepMarker(0, 'ArrowLeft', 3)).toBe(0)
    expect(stepMarker(1, 'ArrowUp', 3)).toBe(0)
    expect(stepMarker(1, 'Home', 3)).toBe(0)
    expect(stepMarker(0, 'End', 3)).toBe(2)
    expect(stepMarker(0, 'a', 3)).toBeNull()
    expect(stepMarker(0, 'ArrowRight', 0)).toBeNull()
  })

  it('places a date inside its year and lists only the kinds present', () => {
    expect(dateToYearPos('2026-01-01')).toBe(2026)
    expect(dateToYearPos('2026-07-02')!).toBeGreaterThan(2026.49)
    expect(dateToYearPos('bad')).toBeNull()
    const lanes = milestoneLanes([
      { ...ms(1)[0]!, kind: 'moratorium' },
      { ...ms(1)[0]!, kind: 'approved' },
    ])
    expect(lanes).toEqual(['approved', 'moratorium'])
  })
})

describe('dumbbell', () => {
  const row = (label: string, a: number, b: number): PeriodRow => ({
    key: label, label, earlier_share: a, later_share: b, earlier_meetings: 1, later_meetings: 1, earlier_recorded: 20, later_recorded: 20,
  })
  const rows = [row('Texas', 0.01, 0.07), row('Ohio', 0.05, 0.04), row('Utah', 0.02, 0.07)]

  it('sorts by the later year, by change and by the earlier year, label breaking ties', () => {
    expect(sortDumbbell(rows, 'later').map((r) => r.label)).toEqual(['Texas', 'Utah', 'Ohio'])
    expect(sortDumbbell(rows, 'change').map((r) => r.label)).toEqual(['Texas', 'Utah', 'Ohio'])
    expect(sortDumbbell(rows, 'earlier').map((r) => r.label)).toEqual(['Ohio', 'Utah', 'Texas'])
    expect(rows[0]!.label).toBe('Texas') // not sorted in place
  })

  it('labels the change in signed percentage points with a true minus', () => {
    expect(ppLabel(0.01, 0.075)).toBe('+6.5 pp')
    expect(ppLabel(0.05, 0.04)).toBe('−1.0 pp')
  })

  it('rounds the axis up to a nice number', () => {
    expect(niceMax(7.4)).toBe(10)
    expect(niceMax(38)).toBe(50)
    expect(niceMax(0)).toBe(1)
  })
})

describe('thin recording coverage (#1207)', () => {
  // National recorded meetings per year, 2026-11-26 (GET /api/topics/guns/timeline): 2024 is a hole in the recordings.
  const NATIONAL: [string, number, number][] = [
    ['2006', 1, 10], ['2007', 0, 13], ['2008', 0, 54], ['2009', 7, 311], ['2010', 7, 1040], ['2011', 29, 1140],
    ['2012', 73, 1874], ['2013', 148, 3205], ['2014', 131, 3831], ['2015', 167, 5239], ['2016', 226, 5985],
    ['2017', 457, 9335], ['2018', 727, 12476], ['2019', 736, 12767], ['2020', 710, 15122], ['2021', 958, 15162],
    ['2022', 1022, 12525], ['2023', 603, 5724], ['2024', 50, 932], ['2025', 598, 14038], ['2026', 980, 16873],
  ]
  const national = NATIONAL.map(([y, m, r]) => yr(y, m, r))

  it('flags the national 2024 hole, not the early ramp', () => {
    const thin = thinYears(national)
    expect([...thin]).toEqual([2024])
  })

  it("doesn't call a state's ramp step a hole (Georgia data centers 2021–26)", () => {
    const ga = [yr('2021', 1, 213), yr('2022', 0, 172), yr('2023', 0, 92), yr('2024', 0, 115), yr('2025', 31, 794), yr('2026', 65, 790)]
    expect([...thinYears(ga)]).toEqual([])
  })

  it('works on a town with a dozen meetings a year', () => {
    const town = [yr('2021', 2, 10), yr('2022', 1, 12), yr('2023', 0, 1), yr('2024', 3, 11), yr('2025', 2, 9)]
    expect([...thinYears(town)]).toEqual([2023])
    expect([...thinYears(town.slice(0, 2))]).toEqual([]) // too few years to judge
  })

  it('catches every year of a long hole, not only its ends', () => {
    const long = [1000, 1000, 100, 100, 100, 100, 1000, 1000].map((n, i) => yr(String(2015 + i), 10, n))
    expect([...thinYears(long)].sort()).toEqual([2017, 2018, 2019, 2020])
  })

  it("stays on counts when a thin year's share rests on too few recorded meetings", () => {
    const town = [yr('2021', 2, 40), yr('2022', 3, 44), yr('2023', 1, 2), yr('2024', 3, 41), yr('2025', 2, 39)]
    expect([...thinYears(town)]).toEqual([2023])
    expect(defaultSeriesMode(town, true)).toBe('meetings')
  })

  it('opens on the share when a drawn year is thin and coverage is known; otherwise on counts', () => {
    expect(defaultSeriesMode(national, true)).toBe('share')
    expect(defaultSeriesMode(national, false)).toBe('meetings')
    expect(defaultSeriesMode(national.filter((y) => y.year !== '2024'), true)).toBe('meetings')
  })

  it('draws the segments either side of a thin year dashed, the rest solid', () => {
    const run = buildSeries(national.filter((y) => Number(y.year) >= 2021), 'meetings')[0]!
    const pieces = splitRun(run, new Set([2024]))
    expect(pieces.map((p) => [p.dashed, p.points.map((q) => q.year)])).toEqual([
      [false, [2021, 2022, 2023]],
      [true, [2023, 2024, 2025]],
      [false, [2025, 2026]],
    ])
  })

  it('hollows a thin year in count mode, and in share mode only a share over too few recorded meetings', () => {
    const [p24] = buildSeries([yr('2024', 50, 932)], 'meetings')[0]!
    expect(isHollow(p24!, 'meetings', new Set([2024]))).toBe(true)
    expect(isHollow(p24!, 'share', new Set([2024]))).toBe(false)
    const [few] = buildSeries([yr('2024', 3, 7)], 'share')[0]!
    expect(isHollow(few!, 'share', new Set())).toBe(true)
  })

  it('names the thin years with their recorded counts', () => {
    expect(thinNote(national, new Set([2024]))).toBe("Only 932 meetings were recorded in 2024, so that year's count is not comparable.")
    expect(thinNote(national, new Set([2007, 2024]))).toBe(
      "Only 13 meetings were recorded in 2007 and 932 in 2024, so those years' counts are not comparable.",
    )
    expect(thinNote(national, new Set())).toBeNull()
  })
})
