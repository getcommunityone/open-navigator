import { describe, expect, it } from 'vitest'
import { assignLanes, evidenceHref, summarize, takeaway } from './rankings'
import type { RankingPlace } from '../api/rankings'

// Test-only fixtures: nothing here is served by the app.
const place = (over: Partial<RankingPlace>): RankingPlace => ({
  jurisdiction_id: 1, jurisdiction_name: 'Testville', state_code: 'AL', size_band: 'mid', population: 60000,
  speakers_for: 4, speakers_against: 14, meetings: 3, against_share: 0.78, shrunk_against_share: 0.7, is_ranked: true,
  band_rank: 1, band_ranked_count: 2, officials_side: null, last_meeting_date: '2026-05-01', ...over,
})

describe('takeaway', () => {
  it('says against / for / split / none from real counts', () => {
    expect(takeaway('Data centers', 31, 23, 8)).toBe('Most places that discussed data centers leaned against: 23 of 31')
    expect(takeaway('Short-term rentals', 10, 3, 7)).toBe('Most places that discussed short-term rentals leaned for: 7 of 10')
    expect(takeaway('Data centers', 10, 5, 5)).toMatch(/^Places were split on data centers/)
    expect(takeaway('Data centers', 23, 23, 0)).toBe('All 23 ranked places that discussed data centers leaned against')
    expect(takeaway('Guns', 1, 0, 1)).toBe('The one ranked place that discussed guns leaned for')
    expect(takeaway('Data centers', 0, 0, 0)).toBe('Too few speakers to rank any place yet on data centers')
  })
  it('keeps names with their own capitals', () => {
    expect(takeaway('ICE detainers', 4, 3, 1)).toContain('discussed ICE detainers')
  })
})

describe('summarize and helpers', () => {
  it('counts leaning among ranked places only and takes their median', () => {
    const s = summarize([
      place({ shrunk_against_share: 0.7 }), place({ shrunk_against_share: 0.3 }), place({ shrunk_against_share: 0.6 }),
      place({ is_ranked: false, shrunk_against_share: 0.99 }),
    ])
    expect(s).toEqual({ ranked: 3, against: 2, for: 1, medianShrunk: 0.6 })
  })
  it('spreads close dots into lanes', () => {
    const lanes = assignLanes([0.5, 0.51, 0.52, 0.9])
    expect(new Set(lanes.slice(0, 3)).size).toBe(3)
  })
  it('links to Browse Topics scoped to the place', () => {
    expect(evidenceHref(7, place({ jurisdiction_name: 'Tuscaloosa' }))).toBe('/browse-topics?topic_id=7&state=AL&city=Tuscaloosa')
  })
})
