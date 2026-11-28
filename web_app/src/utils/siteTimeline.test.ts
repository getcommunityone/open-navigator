import { describe, expect, it } from 'vitest'
import type { SitesTimelineResponse, TimelineSite } from '../api/sitesTimeline'
import {
  appearText,
  capacityText,
  frameLegend,
  operatingText,
  PHASES,
  phaseInYear,
  sitesInYear,
  stripColumns,
  timelineDisplay,
  timelineHeadline,
  undatedCaption,
} from './siteTimeline'

const site = (kw: Partial<TimelineSite>): TimelineSite =>
  ({
    data_center_site_id: 'x', site_name: 'X', source: 'us_data_center_registry', source_name: 'US Data Center Registry',
    appear_year: '2021', appear_basis: 'announced', status: 'operating', ...kw,
  }) as TimelineSite

// The same fixture as tests/test_api_data_center_sites_timeline.py, so the dots and the SQL totals agree.
const FIXTURE: TimelineSite[] = [
  site({ data_center_site_id: 'e1', source: 'epoch', status: 'operating', appear_year: '2020', first_report_year: '2020', operating_year: '2022' }),
  site({ data_center_site_id: 'e2', source: 'epoch', status: 'under_construction', appear_year: '2024', first_report_year: '2025', operating_year: '2028', operating_is_expected: true }),
  site({ data_center_site_id: 'r1', status: 'operating', appear_year: '2021' }),
  site({ data_center_site_id: 'r2', status: 'cancelled', appear_year: '2023' }),
]

const tally = (year: number) => {
  const t: Record<string, number> = {}
  for (const s of sitesInYear(FIXTURE, year)) t[s.phase] = (t[s.phase] ?? 0) + 1
  return t
}

describe('phaseInYear (#1348), mirroring the API SQL', () => {
  it('matches the per-year totals the SQL test checks', () => {
    expect(tally(2019)).toEqual({})
    expect(tally(2020)).toEqual({ under_construction: 1 })
    expect(tally(2021)).toEqual({ under_construction: 1, operating: 1 })
    expect(tally(2022)).toEqual({ operating: 2 })
    expect(tally(2023)).toEqual({ operating: 2, cancelled: 1 })
    expect(tally(2024)).toEqual({ planned: 1, operating: 2, cancelled: 1 })
    expect(tally(2025)).toEqual({ under_construction: 1, operating: 2, cancelled: 1 })
    expect(tally(2028)).toEqual({ operating: 3, cancelled: 1 })
  })

  it('marks the sites first shown in a year, and never places an undated site', () => {
    expect(sitesInYear(FIXTURE, 2023).filter((s) => s.isNew).map((s) => s.site.data_center_site_id)).toEqual(['r2'])
    expect(phaseInYear(site({ appear_year: undefined as unknown as string }), 2030)).toBeNull()
    // #1428: a site with no date at all enters only at today, never before
    const none = site({ appear_year: null, appear_basis: 'none', status: 'planned' })
    expect(phaseInYear(none, 2025, 2026)).toBeNull()
    expect(phaseInYear(none, 2026, 2026)).toBe('planned')
    expect(phaseInYear(none, 2028, 2026)).toBe('planned')
    expect(phaseInYear(site({ status: null }), 2022)).toBe('status_not_published')
  })
})

const res = (kw: Partial<SitesTimelineResponse>): SitesTimelineResponse =>
  ({ scope: { level: 'state' }, available: true, current_year: '2026', total: 10, dated: 10, undated: 0, unplaced: 0, sites: [], years: [], ...kw }) as SitesTimelineResponse

// #1428: every site, by basis. Same VA fixture as the API's SQL test, plus a listed-by site, a no-date site and one unmapped.
const ALL: TimelineSite[] = [
  ...FIXTURE.map((s) => ({ ...s, latitude: 38.9, longitude: -77.4 })),
  site({ data_center_site_id: 'r5', status: 'operating', appear_year: '2026', appear_basis: 'listed_by', listed_on: '2026-07-16', latitude: 37, longitude: -78 }),
  site({ data_center_site_id: 'r3', status: 'planned', appear_year: null, appear_basis: 'none', latitude: 37.5, longitude: -77 }),
  site({ data_center_site_id: 'e3', source: 'epoch', status: 'under_construction', appear_year: '2024', appear_basis: 'epoch_first_report', first_report_year: '2024', latitude: null, longitude: null }),
]
const ALL_YEARS = [2020, 2021, 2022, 2023, 2024, 2025, 2026, 2027, 2028].map((y) => {
  const t: Record<string, number> = { planned: 0, under_construction: 0, operating: 0, cancelled: 0, no_longer_listed: 0, status_not_published: 0 }
  let undated = 0
  const inYear = sitesInYear(ALL, y, 2026)
  for (const s of inYear) {
    t[s.phase]! += 1
    if (s.undated) undated += 1
  }
  return { year: String(y), ...t, total: inYear.length, undated, is_future: y > 2026 }
})
const ALL_RES = res({ total: 7, dated: 5, mapped: 6, not_mapped: 1, undated: 2, unplaced: 1, listed_year: '2026', sites: ALL, years: ALL_YEARS as never })

describe('the legend and strip count every site (#1428)', () => {
  it('sums the legend to the mapped sites in each frame, plus a not-mapped line', () => {
    for (const y of [2020, 2024, 2026, 2028]) {
      const lg = frameLegend(sitesInYear(ALL, y, 2026))
      expect(PHASES.reduce((n, p) => n + lg.byPhase[p], 0)).toBe(lg.mapped)
      expect(lg.mapped + lg.notMapped).toBe(ALL_YEARS.find((r) => r.year === String(y))!.total)
    }
    // today's frame: every mapped site, at its current status; the undated ones are flagged
    const today = frameLegend(sitesInYear(ALL, 2026, 2026))
    expect(today.mapped).toBe(ALL_RES.mapped)
    expect(today.notMapped).toBe(ALL_RES.not_mapped)
    expect(today.mapped + today.notMapped).toBe(ALL_RES.total)
    expect(today.undatedMapped).toBe(2)
    expect(frameLegend(sitesInYear(ALL, 2025, 2026)).undatedMapped).toBe(0)
    // a site the map can't place (a territory off the US map) moves to "not mapped"; the sum still holds
    const offMap = frameLegend(sitesInYear(ALL, 2026, 2026), (s) => s.latitude != null && s.data_center_site_id !== 'r5')
    expect([offMap.mapped, offMap.notMapped, offMap.undatedMapped]).toEqual([5, 2, 1])
    expect(PHASES.reduce((n, p) => n + offMap.byPhase[p], 0)).toBe(offMap.mapped)
  })

  it('splits each strip column into start-dated phases and the undated rest, summing to the API total', () => {
    for (const c of stripColumns(ALL_RES)) {
      expect(PHASES.reduce((n, p) => n + c.dated[p], 0) + c.undated).toBe(c.total)
    }
    const c26 = stripColumns(ALL_RES).find((c) => c.year === 2026)!
    expect(c26.undated).toBe(2)
    expect(c26.total).toBe(7)
  })
})

describe('the screen copy (#1348, #1428)', () => {
  it('headlines every site, with the start-dated and listed-only counts', () => {
    expect(timelineHeadline(res({ total: 2379, dated: 728, undated: 1651, unplaced: 0, listed_year: '2026' }), 'National')).toBe(
      '2,379 data center sites on record across the country: 728 with a known start date, 1,651 listed by 2026 with no earlier date on record',
    )
    expect(timelineHeadline(res({ total: 70, dated: 10, undated: 61, unplaced: 1, listed_year: '2026' }), 'Florida')).toBe(
      '70 data center sites on record in Florida: 10 with a known start date, 60 listed by 2026 with no earlier date on record, 1 with no date on record',
    )
    expect(timelineHeadline(res({ total: 10, dated: 10 }), 'Florida')).toBe('10 data center sites on record in Florida, all with a known start date')
    expect(timelineHeadline(res({ total: 0, dated: 0 }), 'Wyoming')).toBe('No data center sites on record in Wyoming')
  })

  it('captions the undated sites without implying they did not exist earlier', () => {
    expect(undatedCaption(ALL_RES, 2026)).toBe('Plus 2 sites with no start date on record (squares): listed by 2026, they may be older.')
    expect(undatedCaption(ALL_RES, 2024)).toBe(
      '2 more sites have no start date on record and join the map at 2026, the year they were first listed; they may be older.',
    )
    expect(undatedCaption(res({ undated: 0 }), 2026)).toBeNull()
  })

  it('labels a listed-by date as such, never as an opening', () => {
    expect(appearText(ALL[4]!)).toBe('Start date not on record; listed by Jul 16, 2026')
    expect(appearText(ALL[5]!)).toBe('No date on record')
    expect(appearText(ALL[6]!)).toBe('Work first on record in 2024 (Epoch AI)')
  })

  it('uses the shared display rule: 1–5 sites are a list, not an animation', () => {
    expect(timelineDisplay(res({ total: 0 }))).toBe('empty')
    expect(timelineDisplay(res({ total: 4 }))).toBe('list')
    const mixed = [{ year: '2026', planned: 6, under_construction: 1, operating: 1, cancelled: 2, total: 10 }] as never
    expect(timelineDisplay(res({ total: 10, years: mixed }))).toBe('units')
    // one status and under 20 sites: the shared rule lists them
    expect(timelineDisplay(res({ total: 10, years: [{ year: '2026', operating: 10, total: 10 }] as never }))).toBe('list')
    expect(timelineDisplay(res({ total: 2379, years: [{ year: '2026', operating: 2379, total: 2379 }] as never }))).toBe('units')
  })

  it('labels capacity and Epoch’s operating year only when published', () => {
    expect(capacityText(site({ capacity_mw_operational: 48, it_power_mw: 239 }))).toBe('48 MW operating · 239 MW IT power')
    expect(capacityText(site({}))).toBeNull()
    expect(operatingText(site({ operating_year: '2028', operating_is_expected: true }))).toBe('Expected operating 2028 (Epoch AI projection)')
    expect(operatingText(site({}))).toBeNull()
  })
})
