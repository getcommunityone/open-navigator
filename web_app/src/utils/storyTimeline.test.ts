import { describe, expect, it } from 'vitest'
import type { PeriodRow, TimelineMilestone, TimelineYear } from '../api/topicTimeline'
import {
  buildSeries,
  dateToYearPos,
  defaultMarker,
  gapYears,
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
