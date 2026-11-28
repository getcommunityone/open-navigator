import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import StanceGauge from './StanceGauge'
import type { RankingPlace } from '../../api/rankings'

// Test-only fixtures: nothing here is served by the app.
const mk = (id: number, name: string, over: Partial<RankingPlace>): RankingPlace => ({
  jurisdiction_id: id, jurisdiction_name: name, state_code: 'AL', size_band: 'mid', population: 60000,
  speakers_for: 4, speakers_against: 14, meetings: 3, against_share: 0.78, shrunk_against_share: 0.7, is_ranked: true,
  band_rank: 1, band_ranked_count: 3, officials_side: null, last_meeting_date: '2026-05-01', ...over,
})
const places = [
  mk(1, 'Tuscaloosa', { shrunk_against_share: 0.9, against_share: 0.95 }),
  mk(2, 'Forville', { shrunk_against_share: 0.1, against_share: 0.05, speakers_for: 17, speakers_against: 1 }),
  mk(3, 'Smallton', { is_ranked: false, against_share: 0.5, shrunk_against_share: 0.5, speakers_for: 2, speakers_against: 2 }),
]
const xOf = (html: string, name: string) => Number(new RegExp(`data-x="([0-9.]+)"[^>]*aria-label="${name}`).exec(html)?.[1])

describe('StanceGauge', () => {
  const html = renderToStaticMarkup(<StanceGauge topicName="Data centers" places={places} />)
  it('puts against on the left and for on the right', () => {
    expect(xOf(html, 'Tuscaloosa')).toBeCloseTo(0.1, 2)
    expect(xOf(html, 'Forville')).toBeCloseTo(0.9, 2)
  })
  it('draws unranked places light and ranked solid', () => {
    expect((html.match(/data-testid="dot-ranked"/g) ?? []).length).toBe(2)
    expect((html.match(/data-testid="dot-unranked"/g) ?? []).length).toBe(1)
    expect(html).toContain('opacity-70')
  })
  it('marks the median of ranked places and labels the axis and legend', () => {
    expect(html).toContain('data-testid="median-marker"')
    expect(html).toContain('All against')
    expect(html).toContain('All for')
    expect(html).toContain('National median')
    expect(html).not.toContain('officials-badge')
  })
  it('states the takeaway title from the counts', () => {
    expect(html).toContain('Places were split on data centers')
    const against = renderToStaticMarkup(<StanceGauge topicName="Data centers" places={[places[0], mk(4, 'A', {}), places[1]]} />)
    expect(against).toContain('Most places that discussed data centers leaned against: 2 of 3')
    const forward = renderToStaticMarkup(<StanceGauge topicName="Data centers" places={[places[1], mk(5, 'B', { shrunk_against_share: 0.2 }), places[0]]} />)
    expect(forward).toContain('leaned for: 2 of 3')
  })
  it('handles zero ranked places with only light dots and no median', () => {
    const z = renderToStaticMarkup(<StanceGauge topicName="Data centers" places={[places[2]]} />)
    expect(z).toContain('Too few speakers to rank any place yet')
    expect(z).not.toContain('median-marker')
    expect(z).not.toContain('dot-ranked')
  })
  it('gives each dot a screen-reader label and shows an officials badge only when known', () => {
    expect(html).toContain('aria-label="Tuscaloosa, AL: 14 of 18 speakers against"')
    expect(html).toContain('Smallton, AL: 2 of 4 speakers against (too few speakers to rank)')
    const o = renderToStaticMarkup(<StanceGauge topicName="Data centers" places={[mk(9, 'Offville', { officials_side: 'split' })]} />)
    expect(o).toContain('officials-badge')
  })
})
