import { describe, expect, it } from 'vitest'
import {
  DATA_CENTER_STORY,
  STORY_CHARTS,
  challengePath,
  chartScopeLabel,
  contextSourceFor,
  landConcernNote,
  scopeQuery,
  screenText,
  statsScopeNote,
  stopLabel,
  storyScopeLabel,
  storyScreenIndex,
  storyStats,
  type StoryData,
  type StoryScope,
  type StoryStatus,
} from './dataStory'

const nat: StoryScope = { stateName: null, city: null }
const al: StoryScope = { stateCode: 'AL', stateName: 'Alabama', city: null }
const tus: StoryScope = { stateCode: 'AL', stateName: 'Alabama', city: 'Tuscaloosa' }

const scope = { level: 'national', state_code: null, state: null, city: null } as never

// Test data only: this fixture never leaves the test.
const full: StoryData = {
  sites: { scope, city_applied: false, counts: { planned: 4, under_construction: 2, operating: 10, no_longer_listed: 1, status_not_published: 3 }, items: [] } as never,
  projects: {
    scope,
    total: 5,
    items: ['planned', 'planned', 'planned', 'operating', null].map((status, i) => ({ project_id: `p${i}`, project_name: 'n', project_source: 'curated', status, companies: [], figures: [], timeline: [] })),
  } as never,
  'job-claims': { scope, totals: { construction: 12, operations: 7 }, items: [] } as never,
  concerns: {
    scope,
    items: [
      { concern: 'water', mention_count: 30, objection_count: 60, concern_rank: 1, is_dominant: true },
      { concern: 'noise', mention_count: 10, objection_count: 60, concern_rank: 2, is_dominant: false },
    ],
    national: [
      { concern: 'water', mention_count: 30, objection_count: 60, concern_rank: 1, is_dominant: true },
      { concern: 'noise', mention_count: 10, objection_count: 60, concern_rank: 2, is_dominant: false },
    ],
  } as never,
  'meeting-mentions': {
    scope,
    counts: { passages: 5, meetings: 3, site_specific: 0 },
    items: ['2022-01-01', '2023-01-01', '2023-02-01', '2024-01-01', '2024-03-01'].map((d, i) => ({ data_center_meeting_mention_id: `m${i}`, meeting_date: d })),
  } as never,
  'agenda-items': { scope, counts: { upcoming: 2, past: 9 }, items: [] } as never,
  'community-events': {
    scope,
    unconfirmed: 0,
    items: ['town_hall', 'town_hall', 'open_house'].map((event_kind, i) => ({ community_event_id: `c${i}`, event_kind, title: 't' })),
  } as never,
}
const ready: StoryStatus = Object.fromEntries(STORY_CHARTS.map((k) => [k, 'ready'])) as StoryStatus

const BANNED = /\b(because|due to|driven by|good|bad|worrying|best|worst|should|problem|crisis|hates?|loves?|will|expected|likely)\b/i

describe('story structure', () => {
  it('opens on the question, then the place, and ends on the question again; a header is never a number', () => {
    expect(DATA_CENTER_STORY.map((s) => s.id)).toEqual([
      'question',
      'scope',
      'overview',
      'sites',
      'projects',
      'jobs',
      'concerns',
      'meetings',
      'agendas',
      'gatherings',
      'verdict',
    ])
    expect(DATA_CENTER_STORY.slice(0, 2).map((s) => s.kind)).toEqual(['question', 'scope'])
    expect(DATA_CENTER_STORY[DATA_CENTER_STORY.length - 1]!.kind).toBe('verdict')
    for (const s of DATA_CENTER_STORY) expect(s.eyebrow).toMatch(/^[A-Za-z]/)
    expect(new Set(DATA_CENTER_STORY.map((s) => s.id)).size).toBe(DATA_CENTER_STORY.length)
  })
})

describe('the screens around the record', () => {
  const q = { text: 'Should we allow new data centers?', place_text: 'Should {place} allow new data centers?' }
  const at = (id: string) => DATA_CENTER_STORY.find((s) => s.id === id)!
  it('word the question for the place in scope', () => {
    expect(screenText(at('question'), {}, {}, nat, q).headline).toBe('Should we allow new data centers?')
    expect(screenText(at('question'), {}, {}, tus, q).headline).toBe('Should Tuscaloosa allow new data centers?')
    expect(screenText(at('verdict'), {}, {}, al, q).headline).toBe("You've seen the record. Where do you stand now?")
    expect(screenText(at('verdict'), {}, {}, al, q).context).toBe('Should Alabama allow new data centers?')
    expect(screenText(at('scope'), {}, {}, nat, q).headline).toBe('Where?')
  })
  it('state no number and no question that was not loaded', () => {
    for (const id of ['question', 'scope', 'verdict']) {
      const t = screenText(at(id), {}, {}, nat)
      expect(`${t.headline} ${t.context}`).not.toMatch(/\d/)
      expect(t.empty || t.failed).toBe(false)
    }
    expect(screenText(at('question'), {}, {}, nat).headline).toBe('The question')
  })
  it('finds a screen by its id, and an old link by the screen that replaced it', () => {
    expect(storyScreenIndex(DATA_CENTER_STORY, 'question')).toBe(0)
    expect(storyScreenIndex(DATA_CENTER_STORY, 'scope')).toBe(1)
    expect(storyScreenIndex(DATA_CENTER_STORY, 'verdict')).toBe(DATA_CENTER_STORY.length - 1)
    expect(storyScreenIndex(DATA_CENTER_STORY, 'turn')).toBe(DATA_CENTER_STORY.length - 1)
    expect(storyScreenIndex(DATA_CENTER_STORY, 'nope')).toBe(-1)
    expect(storyScreenIndex(DATA_CENTER_STORY, '')).toBe(-1)
  })
})

/** The screens that state the record (the question, place and verdict screens carry no figure). */
const RECORD = DATA_CENTER_STORY.filter((s) => s.kind === 'overview' || s.kind === 'chart')
/** Sentences that describe how the page is built, which the reader does not need (#915). */
const BUILT = /one screen at a time|each dot|scroll|whole-scope|is built from|open navigator records/i

describe('screenText on a full fixture', () => {
  for (const sc of [nat, al, tus]) {
    it(`has no banned wording and no empty text for ${storyScopeLabel(sc)}`, () => {
      for (const s of RECORD) {
        const t = screenText(s, full, ready, sc)
        expect(t.headline.length).toBeGreaterThan(10)
        expect(t.context.length).toBeGreaterThan(5)
        expect(t.headline).not.toMatch(BANNED)
        expect(t.context).not.toMatch(BANNED)
        expect(`${t.headline} ${t.context}`).not.toMatch(BUILT)
        expect(t.headline).not.toMatch(/^\d/)
        expect(t.empty).toBe(false)
      }
    })
  }

  it('states only counts the fixture gives', () => {
    const by = Object.fromEntries(DATA_CENTER_STORY.map((s) => [s.id, screenText(s, full, ready, al)]))
    expect(by.sites!.headline).toBe('Of 20 data center sites in Alabama, 10 are operating, and 6 more are planned or under construction.')
    expect(by.sites!.context).toContain('1 no longer listed and 3 with no published status')
    expect(by.projects!.headline).toBe('Of 5 data center projects on record in Alabama, 3 are listed as planned and 1 listed as operating.')
    expect(by.jobs!.headline).toBe('Meetings in Alabama include 12 claims about construction jobs and 7 claims about operations jobs.')
    expect(by.jobs!.context).toContain('Construction claims outnumber operations claims by 5.')
    expect(by.concerns!.headline).toContain('30 of 40 mentions (75%)')
    expect(by.meetings!.headline).toBe('A data center came up in 3 meetings in Alabama, in 5 quoted passages.')
    expect(by.meetings!.context).toContain('1 passage in 2022, 2 passages in 2024')
    expect(by.agendas!.headline).toContain('Of 11 meeting agendas that name a data center in Alabama, 2 are for upcoming meetings and 9 for past ones.')
    expect(by.gatherings!.headline).toContain('Company-hosted data center meetings listed in Alabama number 3: 2 town halls and 1 open house.')
  })

  it('does not state a share or a change over time from a capped list', () => {
    const capped: StoryData = {
      ...full,
      'meeting-mentions': { ...(full['meeting-mentions'] as object), counts: { passages: 900, meetings: 300, site_specific: 0 } } as never,
    }
    const t = screenText(DATA_CENTER_STORY.find((s) => s.id === 'meetings')!, capped, ready, nat)
    expect(t.context).toContain('most recent 5 passages')
    expect(t.context).not.toContain('By year')
  })

  it('says the sites screen shows the state when a city is chosen', () => {
    const t = screenText(DATA_CENTER_STORY.find((s) => s.id === 'sites')!, full, ready, tus)
    expect(t.headline).toContain('in Alabama')
    expect(t.headline).not.toContain('Tuscaloosa')
    expect(t.context).toContain('listed by state')
    expect(chartScopeLabel('sites', tus)).toBe('Alabama')
    expect(chartScopeLabel('concerns', tus)).toBe('Tuscaloosa, Alabama')
  })
})

describe('empty, loading and failed screens', () => {
  const empty: StoryData = {
    sites: { scope, city_applied: false, counts: { planned: 0, under_construction: 0, operating: 0, no_longer_listed: 0, status_not_published: 0 }, items: [] } as never,
    'job-claims': { scope, totals: { construction: 0, operations: 0 }, items: [] } as never,
    projects: { scope, total: 0, items: [] } as never,
    concerns: { scope, items: [], national: [] } as never,
    'meeting-mentions': { scope, counts: { passages: 0, meetings: 0, site_specific: 0 }, items: [] } as never,
    'agenda-items': { scope, counts: { upcoming: 0, past: 0 }, items: [] } as never,
    'community-events': { scope, unconfirmed: 0, items: [] } as never,
  }
  it('says no data is available for this place and offers to broaden', () => {
    for (const s of RECORD) {
      const t = screenText(s, empty, ready, tus)
      expect(t.empty).toBe(true)
      expect(t.headline).toBe('No data available for this place.')
      expect(stopLabel(s, t)).toBe(s.eyebrow)
    }
    expect(storyStats(empty)).toEqual([])
  })
  it('never invents a number while loading or after a failure', () => {
    const sites = DATA_CENTER_STORY.find((s) => s.id === 'sites')!
    const loading = screenText(sites, {}, {}, nat)
    expect(loading.headline).not.toMatch(/\d/)
    const failed = screenText(sites, {}, { sites: 'error' }, nat)
    expect(failed.failed).toBe(true)
    expect(failed.empty).toBe(false)
    expect(failed.headline).not.toMatch(/\d/)
  })
})

describe('landConcernNote', () => {
  const res = (items: Array<[string, number]>) => ({ items: items.map(([concern, mention_count]) => ({ concern, mention_count })), national: items.map(([concern, mention_count]) => ({ concern, mention_count })) }) as never
  it('says it only when land concerns are really in the data', () => {
    expect(landConcernNote(res([['land', 5], ['noise', 15]]), null)).toBe('Land and property appear in 5 of 20 concern mentions (25%).')
    expect(landConcernNote(res([['noise', 15]]), null)).toBeNull()
    expect(landConcernNote(res([['land', 0], ['noise', 3]]), 'Alabama')).toBeNull()
    expect(landConcernNote(null, null)).toBeNull()
  })
})

describe('context screens', () => {
  it('names the source of every figure-only screen', () => {
    for (const s of DATA_CENTER_STORY.filter((x) => x.kicker)) expect(contextSourceFor(s.chart)).toBeTruthy()
    expect(DATA_CENTER_STORY.filter((x) => x.kicker).map((x) => x.id)).toEqual(['sites', 'projects'])
    expect(contextSourceFor('concerns')).toBeNull()
  })
})

describe('stats and links', () => {
  it('lists only counts the endpoints returned', () => {
    const k = storyStats(full)
    // transcript-based counts first, then record counts from other sources, each naming its source
    expect(k.map((s) => [s.key, s.value])).toEqual([
      ['meetings', 3],
      ['passages', 5],
      ['agendas', 11],
      ['claims', 19],
      ['sites', 20],
      ['projects', 5],
    ])
    expect(k.find((s) => s.key === 'sites')!.label).toContain('Epoch AI')
    expect(k.find((s) => s.key === 'projects')!.label).toContain('Epoch AI')
    // sites alone never lead the opener
    const onlySites = screenText(DATA_CENTER_STORY.find((s) => s.id === 'overview')!, { sites: full.sites }, { sites: 'ready' }, al)
    expect(onlySites.headline).toBe('No meeting records are available for this place.')
    expect(onlySites.headline).not.toMatch(/\d/)
    expect(storyStats({})).toEqual([])
  })
  it('keeps a state-level count honest under a city scope', () => {
    const state = storyStats(full, al)
    expect(state.find((s) => s.key === 'sites')!.label).toBe('data center sites on record, from Epoch AI')
    expect(statsScopeNote(state, al)).toBe('Counts for Alabama.')
    const city = storyStats(full, tus)
    expect(city.find((s) => s.key === 'sites')!.label).toBe('data center sites on record in Alabama, from Epoch AI')
    expect(city.find((s) => s.key === 'meetings')!.label).toBe('meetings where a data center came up')
    expect(statsScopeNote(city, tus)).toContain('except sites')
    expect(statsScopeNote(city, tus)).toContain('Tuscaloosa, Alabama')
    expect(statsScopeNote(city, tus)).toContain('for Alabama')
    // no sites count, nothing to except
    expect(statsScopeNote(city.filter((s) => s.key !== 'sites'), tus)).not.toContain('except')
  })
  it('carries the place in every link', () => {
    expect(scopeQuery(tus)).toBe('?state=AL&city=Tuscaloosa')
    expect(scopeQuery(al)).toBe('?state=AL')
    expect(scopeQuery(nat)).toBe('')
    expect(challengePath('data-centers', tus)).toBe('/challenge/data-centers?state=AL&city=Tuscaloosa')
    expect(storyScopeLabel(nat)).toBe('National')
    expect(storyScopeLabel(tus)).toBe('Tuscaloosa, Alabama')
  })
})
