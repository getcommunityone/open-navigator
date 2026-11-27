import { describe, expect, it } from 'vitest'
import type { TopicUpcomingResponse, UpcomingItem } from '../api/topicUpcoming'
import { broaderHref, nothingUpcoming, upcomingBasisNote, upcomingCardLine, upcomingHeadline, upcomingKindLabel } from './topicUpcoming'
import { outcomeCardHref } from './homeOutcomes'

const item = (over: Partial<UpcomingItem> = {}): UpcomingItem => ({
  upcoming_id: 'u1', kind: 'meeting', match_basis: 'place_discussed_before', date: '2026-12-01', time: null,
  jurisdiction_name: 'Henry County', state_code: 'GA', state: 'Georgia', body_name: null,
  title: 'Board of Commissioners Meeting', location: null, source_url: 'https://youtube.com/watch?v=x',
  source_label: 'Livestream', matched_text: 'a <mark>data center</mark> ordinance', prior_meeting_date: '2026-02-10',
  prior_url: 'https://youtube.com/watch?v=y', tentative: false, ...over,
})

const resp = (over: Partial<TopicUpcomingResponse> = {}): TopicUpcomingResponse => ({
  topic: 'data-centers', topic_id: 100001, state_code: 'GA', state: 'Georgia', city: null, available: true,
  as_of: '2026-11-27', last_updated: null, built_at: null, total: 0,
  counts: { meeting: 0, hearing: 0, deadline: 0, bill_action: 0, event: 0 }, items: [],
  pending_bills: { total: 0, latest_action_seen: null, items: [] }, broader: null, ...over,
})

describe('upcoming words (#1302)', () => {
  it('counts what is on the calendar and names the soonest', () => {
    const d = resp({ total: 6, items: [item()] })
    expect(upcomingHeadline(d, 'data centers', 'Georgia')).toBe(
      '6 meetings and hearings on the calendar in Georgia where data centers could come up, the next on Dec 1.',
    )
    expect(upcomingCardLine(d, 'Georgia')).toBe('Next: Henry County, GA, Dec 1')
  })

  it('says nothing is upcoming, never a stand-in, and points at open bills or the wider scope', () => {
    expect(upcomingHeadline(resp(), 'water fluoridation', 'Georgia')).toBe('Nothing upcoming on record for Georgia.')
    expect(upcomingHeadline(resp({ pending_bills: { total: 1, latest_action_seen: null, items: [] } }), 'water fluoridation', 'Georgia')).toBe(
      'Nothing upcoming on record for Georgia, but 1 state bill is still open.',
    )
    expect(nothingUpcoming('National')).toBe('Nothing upcoming on record yet.')
    const wider = resp({ broader: { state_code: null, label: 'National', total: 1 } })
    expect(upcomingCardLine(wider, 'Georgia')).toBe('Nothing upcoming on record for Georgia; 1 nationally.')
    expect(broaderHref('/stories/water-fluoridation', wider.broader, 'screen=upcoming')).toBe('/stories/water-fluoridation?screen=upcoming')
    expect(broaderHref('/stories/data-centers', { state_code: 'AL', label: 'Alabama', total: 2 }, 'screen=upcoming')).toBe(
      '/stories/data-centers?state=AL&screen=upcoming',
    )
    expect(broaderHref('/x', null)).toBeNull()
  })

  it('says why each item is listed', () => {
    expect(upcomingKindLabel(item())).toBe('Scheduled meeting')
    expect(upcomingKindLabel(item({ kind: 'hearing', match_basis: 'official_notice' }))).toBe('Public hearing')
    expect(upcomingKindLabel(item({ match_basis: 'agenda_text' }))).toBe('On the agenda')
    expect(upcomingBasisNote(item(), 'data centers')).toBe('Agenda not posted yet. Henry County discussed data centers on Feb 10, 2026:')
    expect(upcomingBasisNote(item({ match_basis: 'official_notice', tentative: true }), 'data centers')).toBe(
      'The official notice lists it (the date is tentative).',
    )
  })

  it('home cards open the story at the same place, on their screen', () => {
    expect(outcomeCardHref('water-fluoridation', { stateCode: 'GA', city: null }, 'upcoming')).toBe(
      '/stories/water-fluoridation?state=GA&screen=upcoming',
    )
    expect(outcomeCardHref('data-centers', { stateCode: null, city: 'Ignored' }, 'meetings')).toBe('/stories/data-centers?screen=meetings')
    expect(outcomeCardHref('data-centers', { stateCode: 'AL', city: 'Tuscaloosa' }, 'upcoming')).toBe(
      '/stories/data-centers?state=AL&city=Tuscaloosa&screen=upcoming',
    )
  })
})
