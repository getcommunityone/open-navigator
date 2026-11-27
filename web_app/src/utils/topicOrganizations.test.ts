import { describe, expect, it } from 'vitest'
import type { TopicOrganizationItem, TopicOrganizationsResponse } from '../api/topicOrganizations'
import { pickDisplay } from './displayFit'
import {
  methodCounts,
  noNonprofits,
  nonprofitsHeadline,
  oneLine,
  revenueLine,
  sentenceCase,
  sideLabel,
  whyListed,
} from './topicOrganizations'

const resp = (over: Partial<TopicOrganizationsResponse> = {}): TopicOrganizationsResponse => ({
  topic: 'guns',
  topic_id: 100005,
  state_code: 'AL',
  state: 'Alabama',
  city: null,
  available: true,
  total: 0,
  counts: { named_in_meeting: 0, keyword_in_mission: 0, keyword_in_name: 0, ntee_code: 0, cause_tag: 0 },
  items: [],
  broader: null,
  built_at: null,
  ...over,
})

const item = (over: Partial<TopicOrganizationItem> = {}): TopicOrganizationItem => ({
  master_org_id: 'o1',
  org_name: 'Tuscaloosa Rifle Club',
  city: 'Tuscaloosa',
  state_code: 'AL',
  state: 'Alabama',
  match_method: 'keyword_in_name',
  match_methods: ['keyword_in_name'],
  match_text: null,
  match_source_url: null,
  match_date: null,
  match_place: null,
  mission: null,
  side: null,
  ntee_code: null,
  revenue: null,
  revenue_tax_year: null,
  website_url: null,
  ...over,
})

describe('topic organizations words', () => {
  it('says the empty scope plainly and the display rule picks empty', () => {
    const d = resp()
    expect(nonprofitsHeadline(d, 'guns', 'Alabama')).toBe('No nonprofits on record for Alabama.')
    expect(noNonprofits('National')).toBe('No nonprofits on record yet.')
    expect(pickDisplay({ items: d.total, categories: methodCounts(d).map((r) => r.count) }).kind).toBe('empty')
  })

  it('counts in the headline and names meeting mentions', () => {
    const d = resp({ total: 12, counts: { named_in_meeting: 2, keyword_in_mission: 0, keyword_in_name: 10, ntee_code: 0, cause_tag: 0 } })
    expect(nonprofitsHeadline(d, 'guns', 'Alabama')).toBe('12 nonprofits in Alabama on record working on guns; 2 named in a meeting on it.')
    expect(methodCounts(d).map((r) => r.label)).toEqual(['Named in a meeting', 'Name names it'])
    expect(pickDisplay({ items: d.total, categories: methodCounts(d).map((r) => r.count) }).kind).toBe('sentence')
  })

  it('says why each is listed', () => {
    expect(whyListed(item({ match_method: 'named_in_meeting', match_place: 'Tuscaloosa', match_date: '2026-03-02' }), 'guns')).toBe(
      'Named in a meeting on guns in Tuscaloosa on Mar 2, 2026:',
    )
    expect(whyListed(item({ match_method: 'ntee_code', match_text: 'Crime prevention (IRS category I20)' }), 'guns')).toBe(
      'IRS category: Crime prevention (IRS category I20).',
    )
  })

  it('formats revenue only when there is a figure', () => {
    expect(revenueLine(item())).toBeNull()
    expect(revenueLine(item({ revenue: 1_250_000, revenue_tax_year: '2023' }))).toBe('$1.3M revenue (2023)')
    expect(revenueLine(item({ revenue: 48_000, revenue_tax_year: null }))).toBe('$48K revenue')
  })

  it('reads missions in sentence case, one line', () => {
    expect(sentenceCase('TO PROMOTE THE SPORT OF PICKLEBALL')).toBe('To promote the sport of pickleball')
    expect(sentenceCase('Already Mixed case')).toBe('Already Mixed case')
    expect(sentenceCase('TO IMPROVE <mark>ORAL HEALTH</mark> IN GEORGIA')).toBe('To improve <mark>oral health</mark> in georgia')
    const long = 'word '.repeat(60)
    expect((oneLine(long) ?? '').length).toBeLessThanOrEqual(141)
  })

  it('shows a side only when one is given', () => {
    expect(sideLabel(null)).toBeNull()
    expect(sideLabel('gun rights')).toBe('Gun rights')
  })
})
