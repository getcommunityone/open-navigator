import { describe, expect, it } from 'vitest'
import {
  communityEventKindLabel,
  figureLabel,
  timelineStageLabel,
  concernLabel,
  concernSummary,
  dataCentersTitle,
  formatDateRange,
  formatHeadcount,
  hearItUrl,
  meetingAttribution,
  placeScope,
  siteStatusLabel,
  verifiedLabel,
  siteSourcesText,
  siteTotal,
} from './dataCenterJobs'

describe('formatHeadcount', () => {
  it('says "Not stated" when both bounds are unknown (never 0)', () => {
    expect(formatHeadcount(null, null)).toBe('Not stated')
  })
  it('renders a range', () => {
    expect(formatHeadcount(100, 1500)).toBe('100–1,500 jobs')
  })
  it('renders a single number when low equals high or one bound is missing', () => {
    expect(formatHeadcount(120, 120)).toBe('120 jobs')
    expect(formatHeadcount(50, null)).toBe('At least 50 jobs')
    expect(formatHeadcount(null, 75)).toBe('Up to 75 jobs')
  })
  it('keeps a real zero distinct from unknown', () => {
    expect(formatHeadcount(0, 0)).toBe('0 jobs')
  })
})

describe('placeScope / dataCentersTitle', () => {
  it('is National with no filter', () => {
    expect(dataCentersTitle(placeScope(undefined, undefined))).toBe('Data centers · National')
  })
  it('expands a state code to the full name', () => {
    expect(dataCentersTitle(placeScope('AL', undefined))).toBe('Data centers · Alabama')
  })
  it('uses the city when a city filter is applied', () => {
    expect(dataCentersTitle(placeScope('AL', 'Tuscaloosa'))).toBe('Data centers · Tuscaloosa')
  })
})

describe('formatDateRange / hearItUrl', () => {
  it('says "Dates not stated" when both are null', () => {
    expect(formatDateRange(null, null)).toBe('Dates not stated')
  })
  it('floors the start second in the YouTube link', () => {
    expect(hearItUrl('abc123', 754.9)).toBe('https://www.youtube.com/watch?v=abc123&t=754s')
    expect(hearItUrl(null, 10)).toBeNull()
    expect(hearItUrl('abc123', null)).toBeNull()
  })
})

describe('meetingAttribution (DC-1.2)', () => {
  it('names the governing body when the record has one', () => {
    expect(meetingAttribution('Tuscaloosa City Council')).toBe('At the Tuscaloosa City Council meeting')
  })
  it('never guesses a body', () => {
    expect(meetingAttribution(null)).toBe('Meeting record')
    expect(meetingAttribution('   ')).toBe('Meeting record')
  })
})

describe('verifiedLabel (DC-1.3)', () => {
  it('shows the verified date when fresh', () => {
    expect(verifiedLabel('2026-11-15T14:00:00Z', false)).toBe('Verified Nov 15, 2026')
  })
  it('flags a stale link and keeps its last date', () => {
    expect(verifiedLabel('2026-09-01T00:00:00Z', true)).toBe('Not verified in the last 30 days (last verified Sep 1, 2026)')
  })
  it('says when a link was never verified', () => {
    expect(verifiedLabel(null, true)).toBe('Not verified yet')
  })
})

describe('siteStatusLabel (DC-4.1)', () => {
  it('names each status in plain words', () => {
    expect(siteStatusLabel('planned', 'planned', null)).toBe('Planned')
    expect(siteStatusLabel('under_construction', null, null)).toBe('Under construction')
    expect(siteStatusLabel(null, null, null)).toBe('Status not published')
  })
  it('keeps a site the source dropped, with when it was last seen', () => {
    expect(siteStatusLabel('no_longer_listed', 'operating', '2026-10-01')).toBe(
      'No longer listed by the source · last seen Oct 1, 2026 · last known: operating',
    )
  })
})

describe('concerns (DC-4.3)', () => {
  it('puts concern keys in plain words', () => {
    expect(concernLabel('electricity')).toBe('electricity costs')
    expect(concernLabel('water')).toBe('water')
  })
  it('summarizes real counts and stays silent without them', () => {
    expect(concernSummary({ concern: 'water', mention_count: 3, objection_count: 4 })).toBe(
      'water in 3 of 4 objections (75%)',
    )
    expect(concernSummary(null)).toBeNull()
    expect(concernSummary({ concern: 'water', mention_count: 0, objection_count: 0 })).toBeNull()
  })
})

describe('community events and project figures (#532)', () => {
  it('labels meeting kinds and timeline stages', () => {
    expect(communityEventKindLabel('town_hall')).toBe('Town hall')
    expect(communityEventKindLabel('unknown')).toBe('Meeting')
    expect(timelineStageLabel('vote')).toBe('Council vote')
    expect(timelineStageLabel('company_meeting')).toBe('Company meeting')
  })
  it('renders a figure in the units its source states', () => {
    expect(figureLabel('investment_usd', 3_200_000_000, 'usd')).toBe('$3.2 billion investment')
    expect(figureLabel('it_mw', 210, 'mw')).toBe('210 MW IT load')
    expect(figureLabel('square_feet', 1_260_000, 'sq_ft')).toBe('1,260,000 sq ft')
  })
})

describe('sites from two inventories (#958)', () => {
  it('labels a cancelled site as the source says so', () => {
    expect(siteStatusLabel('cancelled', 'cancelled', null)).toBe('Cancelled (per the source)')
  })
  it('names only the sources the listed sites come from', () => {
    expect(siteSourcesText([{ source: 'epoch' }, {}])).toBe('Epoch AI')
    expect(siteSourcesText([{ source: 'us_data_center_registry' }])).toBe('the US Data Center Registry')
    expect(siteSourcesText([{ source: 'epoch' }, { source: 'us_data_center_registry' }])).toBe('Epoch AI and the US Data Center Registry')
    expect(siteSourcesText([])).toBeNull()
  })
  it('counts every status once, cancelled included, and treats a missing cancelled count as zero', () => {
    const k = { planned: 2, under_construction: 3, operating: 5, no_longer_listed: 1, status_not_published: 0 }
    expect(siteTotal(k)).toBe(11)
    expect(siteTotal({ ...k, cancelled: 4 })).toBe(15)
    expect(siteTotal(null)).toBe(0)
  })
})
