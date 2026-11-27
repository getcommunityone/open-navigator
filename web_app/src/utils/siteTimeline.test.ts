import { describe, expect, it } from 'vitest'
import type { SitesTimelineResponse, TimelineSite } from '../api/sitesTimeline'
import { phaseInYear, sitesInYear, timelineDisplay, timelineHeadline, undatedNote, capacityText, operatingText } from './siteTimeline'

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
    expect(phaseInYear(site({ status: null }), 2022)).toBe('status_not_published')
  })
})

const res = (kw: Partial<SitesTimelineResponse>): SitesTimelineResponse =>
  ({ scope: { level: 'state' }, available: true, current_year: '2026', dated: 10, undated: 0, sites: [], years: [], ...kw }) as SitesTimelineResponse

const yr = (year: string, total: number, operating = 0, is_future = false) => ({ year, total, operating, is_future })

describe('the screen copy (#1348)', () => {
  it('states the real totals, first year to now, and Epoch’s expected openings', () => {
    expect(timelineHeadline(res({ years: [yr('2012', 1), yr('2026', 10)] as never }), 'Florida')).toBe(
      'From 1 data center site on record in Florida in 2012 to 10 by 2026',
    )
    expect(
      timelineHeadline(res({ years: [yr('1999', 1, 1), yr('2026', 728, 167), yr('2028', 728, 179, true)] as never }), 'National'),
    ).toBe('From 1 data center site on record across the country in 1999 to 728 by 2026, 179 expected operating by 2028')
    expect(timelineHeadline(res({ years: [] }), 'Wyoming')).toBe('No dated data center sites on record in Wyoming')
  })

  it('footnotes the undated sites by status', () => {
    expect(undatedNote(res({ undated: 60, undated_by_status: { operating: 47, planned: 6, cancelled: 5, under_construction: 2 } }))).toBe(
      "60 sites have no date on record (47 operating, 6 proposed, 5 cancelled, 2 under construction), so they aren't placed on the timeline.",
    )
    expect(undatedNote(res({ undated: 1, undated_by_status: { operating: 1 } }))).toBe("1 site has no date on record, so it isn't placed on the timeline.")
    expect(undatedNote(res({ undated: 0 }))).toBeNull()
  })

  it('uses the shared display rule: 1–5 dated sites are a list, not an animation', () => {
    expect(timelineDisplay(res({ dated: 0 }))).toBe('empty')
    expect(timelineDisplay(res({ dated: 4 }))).toBe('list')
    const mixed = [{ year: '2026', planned: 6, under_construction: 1, operating: 1, cancelled: 2, total: 10 }] as never
    expect(timelineDisplay(res({ dated: 10, years: mixed }))).toBe('units')
    // one status and under 20 sites: the shared rule lists them
    expect(timelineDisplay(res({ dated: 10, years: [{ year: '2026', operating: 10, total: 10 }] as never }))).toBe('list')
    expect(timelineDisplay(res({ dated: 728, years: [{ year: '2026', operating: 728, total: 728 }] as never }))).toBe('units')
  })

  it('labels capacity and Epoch’s operating year only when published', () => {
    expect(capacityText(site({ capacity_mw_operational: 48, it_power_mw: 239 }))).toBe('48 MW operating · 239 MW IT power')
    expect(capacityText(site({}))).toBeNull()
    expect(operatingText(site({ operating_year: '2028', operating_is_expected: true }))).toBe('Expected operating 2028 (Epoch AI projection)')
    expect(operatingText(site({}))).toBeNull()
  })
})
