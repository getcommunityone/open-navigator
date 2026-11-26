import { describe, expect, it } from 'vitest'
import type { GroupResult } from '../api/stance'
import {
  COUNT_DOT_CAP,
  chartSpec,
  countDots,
  dotMeaning,
  dotRatio,
  speakerCounts,
  dotGroupHeading,
  findingAgendaItems,
  findingCommunityEvents,
  findingConcerns,
  findingDecisions,
  findingFor,
  findingJobClaims,
  findingMeetingMentions,
  findingProjects,
  findingSites,
  placeLabel,
  resultBars,
  roundHeadline,
  roundWord,
  sidedWith,
  tallySided,
} from './stanceGame'

const grp = (agree: number, disagree: number, unsure: number): GroupResult => ({
  available: true,
  n: agree + disagree + unsure,
  agree,
  disagree,
  unsure,
})
const none = (n: number): GroupResult => ({ available: false, n, agree: null, disagree: null, unsure: null })

describe('resultBars', () => {
  it('returns null for unavailable or missing groups', () => {
    expect(resultBars(none(12))).toBeNull()
    expect(resultBars(none(0))).toBeNull()
    expect(resultBars(null)).toBeNull()
    expect(resultBars(undefined)).toBeNull()
  })
  it('widths sum to 100 by largest remainder', () => {
    const bars = resultBars(grp(1, 1, 1))!
    expect(bars.map((b) => b.percent).reduce((a, b) => a + b, 0)).toBe(100)
    expect(bars.map((b) => b.count)).toEqual([1, 1, 1])
    const b2 = resultBars(grp(50, 30, 20))!
    expect(b2.map((b) => b.percent)).toEqual([50, 30, 20])
    const b3 = resultBars(grp(17, 11, 5))!
    expect(b3.map((b) => b.percent).reduce((a, b) => a + b, 0)).toBe(100)
  })
  it('keeps the answer order agree, disagree, not sure', () => {
    expect(resultBars(grp(3, 2, 1))!.map((b) => b.label)).toEqual(['Agree', 'Disagree', 'Not sure'])
  })
  it('handles a group where all answers are one choice', () => {
    expect(resultBars(grp(40, 0, 0))!.map((b) => b.percent)).toEqual([100, 0, 0])
  })
})

describe('sidedWith', () => {
  it('majority, minority and tie', () => {
    expect(sidedWith('agree', grp(20, 10, 5))).toBe('majority')
    expect(sidedWith('disagree', grp(20, 10, 5))).toBe('minority')
    expect(sidedWith('agree', grp(15, 15, 5))).toBe('tie')
    expect(sidedWith('disagree', grp(15, 15, 5))).toBe('tie')
  })
  it('null for not sure, no answer and unavailable groups', () => {
    expect(sidedWith('unsure', grp(20, 10, 5))).toBeNull()
    expect(sidedWith(null, grp(20, 10, 5))).toBeNull()
    expect(sidedWith('agree', none(29))).toBeNull()
    expect(sidedWith('agree', null)).toBeNull()
  })
  it('compares not sure as a group too', () => {
    expect(sidedWith('agree', grp(10, 5, 20))).toBe('minority')
  })
})

describe('tallySided', () => {
  it('counts only available groups and skips ties', () => {
    const t = tallySided([
      { answer: 'agree', group: grp(20, 10, 5) },
      { answer: 'disagree', group: grp(20, 10, 5) },
      { answer: 'agree', group: none(3) },
      { answer: 'agree', group: grp(5, 5, 0) },
      { answer: 'unsure', group: grp(20, 10, 5) },
    ])
    expect(t).toEqual({ compared: 2, withLarger: 1 })
  })
})

describe('roundWord', () => {
  it('words up to twenty then numerals', () => {
    expect(roundWord(1)).toBe('one')
    expect(roundWord(8)).toBe('eight')
    expect(roundWord(20)).toBe('twenty')
    expect(roundWord(21)).toBe('21')
  })
})

describe('placeLabel', () => {
  it('states exactly the scope', () => {
    expect(placeLabel(null, null)).toBe('National only')
    expect(placeLabel('Alabama', null)).toBe('Alabama')
    expect(placeLabel('Alabama', 'Tuscaloosa')).toBe('Tuscaloosa, Alabama')
  })
})

describe('findings', () => {
  it('job claims', () => {
    const res = { totals: { construction: 12, operations: 1300 }, items: [] } as never
    expect(findingJobClaims(res)).toBe('Meetings nationally include 12 jobs claims for construction and 1,300 for operations.')
    expect(findingJobClaims({ totals: { construction: 0, operations: 0 }, items: [] } as never)).toBeNull()
    expect(findingJobClaims(null)).toBeNull()
  })
  it('sites', () => {
    const res = { counts: { planned: 2, under_construction: 3, operating: 5, no_longer_listed: 1, status_not_published: 0 }, items: [] } as never
    expect(findingSites(res, 'Virginia')).toContain('Of 11 data center sites on record in Virginia, 5 are operating, 3 under construction and 2 planned.')
    expect(findingSites({ counts: { planned: 0, under_construction: 0, operating: 0, no_longer_listed: 0, status_not_published: 0 }, items: [] } as never)).toBeNull()
  })
  it('concerns uses the area list for a state and the national list otherwise', () => {
    const res = {
      items: [{ concern: 'noise', mention_count: 4 }],
      national: [
        { concern: 'water', mention_count: 30 },
        { concern: 'noise', mention_count: 10 },
      ],
    } as never
    expect(findingConcerns(res)).toBe('Water was the #1 concern in meetings nationally: 30 of 40 mentions.')
    expect(findingConcerns(res, 'Alabama')).toBe('Noise was the #1 concern in meetings in Alabama: 4 of 4 mentions.')
    expect(findingConcerns({ items: [], national: [] } as never, 'Alabama')).toBeNull()
    expect(findingConcerns({ items: [], national: [{ concern: 'water', mention_count: 5 }, { concern: 'noise', mention_count: 5 }] } as never)).toBe(
      'Noise and water tied as the most raised concerns in meetings nationally: 5 mentions each of 10.',
    )
  })
  it('meeting mentions', () => {
    const res = {
      counts: { passages: 40 },
      items: [{ meeting_date: '2025-03-01' }, { meeting_date: '2025-04-01' }, { meeting_date: '2024-01-01' }, { meeting_date: null }],
    } as never
    expect(findingMeetingMentions(res)).toBe(
      'The year 2025 has the most meeting passages about data centers nationally: 2 of the 3 most recent (40 passages on record nationally).',
    )
    expect(findingMeetingMentions({ counts: { passages: 0 }, items: [] } as never)).toBeNull()
  })
  it('agenda items', () => {
    expect(findingAgendaItems({ counts: { upcoming: 2, past: 5 }, items: [] } as never)).toBe(
      'Of 7 meeting agendas that mention a data center nationally, 2 are upcoming and 5 past.',
    )
    expect(findingAgendaItems({ counts: { upcoming: 0, past: 0 }, items: [] } as never)).toBeNull()
  })
  it('community events', () => {
    const res = { items: [{ event_kind: 'town_hall' }, { event_kind: 'town_hall' }, { event_kind: 'open_house' }] } as never
    expect(findingCommunityEvents(res)).toBe('Town hall is the most common company-hosted meeting nationally: 2 of 3 events.')
    expect(findingCommunityEvents({ items: [] } as never)).toBeNull()
  })
  it('projects', () => {
    const res = { total: 5, items: [{ status: 'planned' }, { status: 'planned' }, { status: null }] } as never
    expect(findingProjects(res)).toBe('Most data center projects nationally are listed as "Planned": 2 of 3 shown (5 on record).')
    expect(findingProjects({ total: 0, items: [] } as never)).toBeNull()
  })
  it('findingFor dispatches and tolerates unknown keys', () => {
    expect(findingFor('nope', {} as never)).toBeNull()
    expect(findingFor('sites', null)).toBeNull()
  })
})

describe('chartSpec', () => {
  it('null when empty', () => {
    expect(chartSpec('sites', { counts: { planned: 0, under_construction: 0, operating: 0, no_longer_listed: 0, status_not_published: 0 }, items: [] } as never)).toBeNull()
    expect(chartSpec('community-events', { items: [] } as never)).toBeNull()
    expect(chartSpec('projects', { total: 0, items: [] } as never)).toBeNull()
    expect(chartSpec('x', {} as never)).toBeNull()
  })
  it('meeting mentions are dots grouped by year, newest first, one dot per record, with a cap note and a source link', () => {
    const spec = chartSpec('meeting-mentions', {
      counts: { passages: 9 },
      items: [
        { data_center_meeting_mention_id: 'a', meeting_date: '2025-03-01', video_url: 'https://v/1', jump_url: 'https://v/1?t=5', jurisdiction_name: 'Tuscaloosa', state_code: 'AL' },
        { data_center_meeting_mention_id: 'b', meeting_date: '2024-01-01', video_url: 'https://v/2' },
        { data_center_meeting_mention_id: 'c', meeting_date: '2025-05-05', video_url: 'https://v/3' },
      ],
    } as never)!
    expect(spec.kind).toBe('dots')
    if (spec.kind !== 'dots') return
    expect(spec.groups.map((g) => [g.label, g.shown])).toEqual([['2025', 2], ['2024', 1]])
    // the endpoint has no per-year counts: no totals and no shares, only what is shown
    expect(spec.groups.map((g) => [g.total, g.share, g.heading])).toEqual([[null, null, '2025 · 2 shown'], [null, null, '2024 · 1 shown']])
    expect(spec.grandTotal).toBeNull()
    expect(spec.groups[0]!.dots[0]).toMatchObject({ id: 'a', place: 'Tuscaloosa, AL', url: 'https://v/1?t=5' })
    expect(spec.note).toBe('Showing the most recent 3 of 9.')
    expect(spec.drawn).toBe(3)
  })
  it('agenda items split upcoming and past; a dot without a document has no link', () => {
    const spec = chartSpec('agenda-items', {
      counts: { upcoming: 1, past: 1 },
      items: [
        { data_center_agenda_item_id: 'u', is_upcoming: true, document_url: 'https://d/1' },
        { data_center_agenda_item_id: 'p', is_upcoming: false, document_url: null },
      ],
    } as never)!
    if (spec.kind !== 'dots') throw new Error('dots')
    expect(spec.groups.map((g) => g.label)).toEqual(['Upcoming meetings', 'Past meetings'])
    expect(spec.groups[1]!.dots[0]!.url).toBeNull()
    expect(spec.note).toBeNull()
  })
  it('sites are grouped by status in a fixed order', () => {
    const spec = chartSpec('sites', {
      counts: { planned: 1, under_construction: 0, operating: 2, no_longer_listed: 0, status_not_published: 0 },
      items: [
        { data_center_site_id: '1', site_name: 'A', status: 'planned', source_url: 'https://s/1' },
        { data_center_site_id: '2', site_name: 'B', status: 'operating', source_url: 'https://s/2' },
        { data_center_site_id: '3', site_name: 'C', status: 'operating', source_url: '' },
      ],
    } as never)!
    if (spec.kind !== 'dots') throw new Error('dots')
    expect(spec.groups.map((g) => [g.label, g.shown])).toEqual([['Operating', 2], ['Planned', 1]])
    expect(spec.groups[0]!.dots[1]!.url).toBeNull()
  })
  it('concerns: one dot per mention, sorted by mentions, with real counts and shares', () => {
    const spec = chartSpec('concerns', { items: [], national: [{ concern: 'noise', mention_count: 2 }, { concern: 'water', mention_count: 9 }] } as never)!
    expect(spec.groups.map((g) => [g.total, g.shown, g.share])).toEqual([[9, 9, 82], [2, 2, 18]])
    expect(spec.perDot).toBe(1)
    expect(spec.dotMeans).toBe('Every dot is one mention.')
    expect(spec.groups[0]!.heading).toMatch(/· 9 mentions · 82%$/)
  })
  it('job claims: one dot per listed claim, shares only from the whole-scope totals', () => {
    const claim = (id: string, phase: string, extra = {}) => ({ job_claim_id: id, phase, quote: 'q', event_meeting_id: 1, ...extra })
    const spec = chartSpec('job-claims', {
      totals: { construction: 3, operations: 1 },
      items: [claim('a', 'construction', { video_id: 'vid', start_seconds: 61.9 }), claim('b', 'operations')],
    } as never)!
    expect(spec.groups.map((g) => g.heading)).toEqual(['Construction jobs · 3 records · 75% · showing 1', 'Operations jobs · 1 record · 25%'])
    expect(spec.groups[0]!.dots[0]!.url).toBe('https://www.youtube.com/watch?v=vid&t=61s')
    expect(spec.groups[1]!.dots[0]!.url).toBeNull()
    expect(spec.note).toBe('Showing the most recent 2 of 4.')
    expect(chartSpec('job-claims', { totals: { construction: 0, operations: 0 }, items: [] } as never)).toBeNull()
  })
  it('projects: one dot per listed project; no share, because the endpoint has no count per status', () => {
    const spec = chartSpec('projects', {
      total: 5,
      items: [
        { project_id: 'p1', project_name: 'One', status: 'planned', source_url: 'https://s/1' },
        { project_id: 'p2', project_name: 'Two', status: 'planned', source_url: 'https://s/2' },
        { project_id: 'p3', project_name: 'Three', status: null, source_url: '' },
      ],
    } as never)!
    expect(spec.groups.map((g) => g.heading)).toEqual(['Planned · 2 shown', 'Status not published · 1 shown'])
    expect(spec.grandTotal).toBeNull()
    expect(spec.note).toBe('Showing 3 of 5 projects.')
  })
})

describe('dots drawn from a count', () => {
  const pos = (t: Record<string, number | null>, available = true) =>
    ({ available, totals: { meetings: 1, meetings_reviewed: 1, decisions_with_tally: 0, votes_for: null, votes_against: null, speakers_neutral: 0, ...t }, quotes: { for: [], against: [], question: [] } }) as never
  it('picks the smallest round ratio that fits, and 1 when the count fits', () => {
    expect(dotRatio(0)).toBe(1)
    expect(dotRatio(240)).toBe(1)
    expect(dotRatio(241)).toBe(2)
    expect(dotRatio(1859)).toBe(10)
    expect(dotRatio(6323)).toBe(50)
    expect(dotRatio(100000)).toBe(500)
  })
  it('weights always add up to the real count; only the last dot is the remainder', () => {
    for (const [n, per] of [[1859, 10], [7, 1], [20, 10], [9, 10]] as const) {
      const d = countDots('k', n, per, ['meeting', 'meetings'])
      expect(d.reduce((a, x) => a + (x.weight ?? 1), 0)).toBe(n)
      expect(d.slice(0, -1).every((x) => (x.weight ?? 1) === per)).toBe(true)
    }
    expect(countDots('k', 1859, 10, ['meeting', 'meetings'])).toHaveLength(186)
    expect(countDots('k', 1859, 10, ['meeting', 'meetings'])[185]!.title).toBe('9 meetings')
    expect(countDots('k', 0, 1, ['meeting', 'meetings'])).toEqual([])
  })
  it('says what a dot stands for', () => {
    expect(dotMeaning(1, ['speaker', 'speakers'])).toBe('Every dot is one speaker.')
    expect(dotMeaning(10, ['meeting', 'meetings'])).toBe('Each dot is 10 meetings; the last dot of a group is what is left over.')
  })
  it('positions: one dot per speaker, a tone per stance, shares from the real totals', () => {
    const spec = chartSpec('positions', pos({ speakers_for: 6, speakers_against: 14, speakers_question: 4, speakers_neutral: 0 }))!
    expect(spec.groups.map((g) => [g.tone, g.label, g.shown, g.share])).toEqual([
      ['for', 'Spoke for', 6, 25],
      ['against', 'Spoke against', 14, 58],
      ['question', 'Asked a question', 4, 17],
    ])
    expect(spec.drawn).toBe(24)
    expect(spec.groups[1]!.heading).toBe('Spoke against · 14 speakers · 58%')
    expect(spec.dotMeans).toBe('Every dot is one speaker.')
  })
  it('positions: nothing to draw when no speaker is on record, or the table is not loaded', () => {
    expect(chartSpec('positions', pos({ speakers_for: 0, speakers_against: 0, speakers_question: 0 }))).toBeNull()
    expect(chartSpec('positions', pos({ speakers_for: 6, speakers_against: 1, speakers_question: 0 }, false))).toBeNull()
    expect(speakerCounts(pos({ speakers_for: null, speakers_against: null, speakers_question: null }))).toBeNull()
  })
  it('a count too large to draw one for one is drawn at an exact ratio and never says "showing"', () => {
    const spec = chartSpec('meeting-mentions', { counts: { passages: 6323, meetings: 1859, site_specific: 0 }, items: [] } as never, null, 'meetings')!
    expect(spec.perDot).toBe(10)
    expect(spec.drawn).toBe(186)
    expect(spec.groups[0]!.heading).toBe('Meetings where a data center came up · 1,859 meetings')
    expect(spec.groups[0]!.dots.reduce((a, d) => a + (d.weight ?? 1), 0)).toBe(1859)
    expect(spec.drawn).toBeLessThanOrEqual(COUNT_DOT_CAP)
    const big = chartSpec('concerns', { items: [], national: [{ concern: 'noise', mention_count: 700 }, { concern: 'water', mention_count: 501 }] } as never)!
    expect(big.drawn).toBeLessThanOrEqual(COUNT_DOT_CAP)
    expect(big.groups.map((g) => g.dots.reduce((a, d) => a + (d.weight ?? 1), 0))).toEqual([700, 501])
  })
})

describe('dotGroupHeading', () => {
  it('full data: real count and real share, nothing about drawing', () => {
    expect(dotGroupHeading({ label: 'Operating', shown: 6, total: 6, grandTotal: 10 })).toBe('Operating · 6 records · 60%')
    expect(dotGroupHeading({ label: 'Planned', shown: 1, total: 1, grandTotal: 10 })).toBe('Planned · 1 record · 10%')
  })
  it('capped with real counts: the real count and share, plus how many are drawn', () => {
    expect(dotGroupHeading({ label: 'Operating', shown: 24, total: 118, grandTotal: 197 })).toBe('Operating · 118 records · 60% · showing 24')
  })
  it('capped without counts: only what is shown, never a share or total', () => {
    expect(dotGroupHeading({ label: '2025', shown: 24, total: null, grandTotal: null })).toBe('2025 · 24 shown')
    expect(dotGroupHeading({ label: '2025', shown: 24, total: null, grandTotal: 197 })).toBe('2025 · 24 shown')
  })
  it('zero', () => {
    expect(dotGroupHeading({ label: 'Past', shown: 0, total: 0, grandTotal: 10 })).toBe('Past · 0 records · 0%')
    expect(dotGroupHeading({ label: 'Past', shown: 0, total: null, grandTotal: null })).toBe('Past · 0 shown')
    expect(dotGroupHeading({ label: 'Past', shown: 0, total: 0, grandTotal: 0 })).toBe('Past · 0 records')
  })
})

describe('headline and chart agree on a capped list', () => {
  const sites = {
    counts: { planned: 41, under_construction: 23, operating: 118, no_longer_listed: 6, status_not_published: 9 },
    items: [
      ...Array.from({ length: 5 }, (_, i) => ({ data_center_site_id: 'o' + i, site_name: 'O', status: 'operating', source_url: '' })),
      ...Array.from({ length: 2 }, (_, i) => ({ data_center_site_id: 'p' + i, site_name: 'P', status: 'planned', source_url: '' })),
    ],
  } as never
  it('sites: heading counts are the whole-scope counts, not the drawn ones, and match the headline', () => {
    const spec = chartSpec('sites', sites)!
    if (spec.kind !== 'dots') throw new Error('dots')
    const heads = spec.groups.map((g) => g.heading)
    expect(heads).toContain('Operating · 118 records · 60% · showing 5')
    expect(heads).toContain('Under construction · 23 records · 12% · showing 0')
    expect(spec.grandTotal).toBe(197)
    expect(spec.note).toBe('Showing the most recent 7 of 197.')
    const sentence = findingSites(sites)!
    for (const n of ['197', '118', '23', '41']) expect(sentence).toContain(n)
    expect(spec.groups.find((g) => g.key === 'operating')!.total).toBe(118)
    expect(spec.groups.find((g) => g.key === 'planned')!.total).toBe(41)
  })
  it('agenda items: headings carry the real upcoming and past counts', () => {
    const agenda = {
      counts: { upcoming: 7, past: 52 },
      items: [{ data_center_agenda_item_id: 'u', is_upcoming: true }, { data_center_agenda_item_id: 'p', is_upcoming: false }],
    } as never
    const spec = chartSpec('agenda-items', agenda)!
    if (spec.kind !== 'dots') throw new Error('dots')
    expect(spec.groups.map((g) => g.heading)).toEqual(['Upcoming meetings · 7 records · 12% · showing 1', 'Past meetings · 52 records · 88% · showing 1'])
    expect(findingAgendaItems(agenda)).toBe('Of 59 meeting agendas that mention a data center nationally, 7 are upcoming and 52 past.')
  })
  it('a group with a real count but no drawn dots still gets its heading', () => {
    const spec = chartSpec('sites', { counts: { planned: 0, under_construction: 0, operating: 10, no_longer_listed: 5, status_not_published: 0 }, items: [{ data_center_site_id: 'o', site_name: 'O', status: 'operating', source_url: '' }] } as never)!
    if (spec.kind !== 'dots') throw new Error('dots')
    expect(spec.groups.map((g) => g.heading)).toEqual(['Operating · 10 records · 67% · showing 1', 'No longer listed · 5 records · 33% · showing 0'])
  })
})

describe('roundHeadline', () => {
  it('uses the finding, or a neutral description of the chart', () => {
    expect(roundHeadline('sites', 'X.')).toEqual({ text: 'X.', isFinding: true })
    expect(roundHeadline('sites', null)).toEqual({ text: 'Data center sites on record, by status', isFinding: false })
  })
})

describe('decisions chart (#933)', () => {
  const res = {
    scope: { level: 'state', state_code: 'GA', state: 'Georgia', city: null, jurisdiction_id: null },
    available: true,
    counts: { contested: 1, uncontested: 2, meetings: 2 },
    items: [
      { data_center_decision_id: 'd1', contested: true, headline: 'Data center rezoning approved', meeting_date: '2026-03-02', jurisdiction_name: 'Testville', state_code: 'GA', video_url: 'https://y/v1', decision_url: '/decisions/d1' },
      { data_center_decision_id: 'u1', contested: false, headline: 'Temporary moratorium on data centers', outcome: 'Tabled', vote_text: 'voice vote', meeting_date: '2026-02-01', jurisdiction_name: 'Testville', state_code: 'GA', video_url: 'https://y/v2', decision_url: null },
      { data_center_decision_id: 'u2', contested: false, headline: null, meeting_date: null, jurisdiction_name: null, state_code: 'GA', video_url: null, decision_url: null },
    ],
  }

  it('says how many were debated and how many taken up without debate, from the counts only', () => {
    expect(findingDecisions(res as never, 'Georgia')).toBe('Of 3 decisions on a data center item in Georgia, 1 was debated and 2 were taken up without debate.')
    expect(findingDecisions({ ...res, available: false } as never)).toBeNull()
    expect(findingDecisions({ ...res, counts: { contested: 0, uncontested: 0, meetings: 0 } } as never)).toBeNull()
    expect(findingDecisions({ ...res, counts: {} } as never)).toBeNull()
  })

  it('draws one dot per decision, debated vs taken up without debate, linked to the page or the recording', () => {
    const spec = chartSpec('decisions', res as never) as { kind: string; groups: { key: string; dots: { id: string; url: string | null; title: string }[] }[] }
    expect(spec.kind).toBe('dots')
    const by = Object.fromEntries(spec.groups.map((g) => [g.key, g.dots]))
    expect(by.contested!.map((d) => d.id)).toEqual(['d1'])
    expect(by.contested![0]!.url).toBe('/decisions/d1')
    expect(by.uncontested!.map((d) => d.id)).toEqual(['u1', 'u2'])
    expect(by.uncontested![0]!.url).toBe('https://y/v2')
    // the outcome as recorded, so an item tabled without debate never reads as passed
    expect(by.uncontested![0]!.title).toBe('Temporary moratorium on data centers · Tabled')
    // no headline: a neutral title, never an invented one
    expect(by.uncontested![1]!.title).toBe('Decision on a data center item')
    expect(by.uncontested![1]!.url).toBeNull()
  })
})
