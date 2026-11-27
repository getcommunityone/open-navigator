import { describe, expect, it } from 'vitest'
import {
  changeLabel,
  filterTopics,
  parseTopicFilter,
  parseYoySort,
  relChange,
  scopeQuery,
  splitTopics,
  topicDestination,
  yearBLabel,
} from './topicsYoy'
import type { YoyTopic } from '../api/topicsYoy'

// Test-only rows: nothing here is served by the app.
const t = (
  slug: string,
  ma: number,
  mb: number,
  comparable = true,
  ra = 1000,
  rb = 2000,
  hasStory = true,
  topicId = 1,
): YoyTopic => ({
  topic_id: topicId,
  slug,
  name: slug,
  source: hasStory ? 'curated' : 'civicsearch',
  has_story: hasStory,
  year_a: '2025',
  year_b: '2026',
  meetings_a: ma,
  meetings_b: mb,
  recorded_a: ra,
  recorded_b: rb,
  share_a: ma / ra,
  share_b: mb / rb,
  comparable,
})

describe('Browse all topics (#1343, #1361)', () => {
  it('labels a partial year by its months', () => {
    expect(yearBLabel({ year_b: '2026', year_b_through: '2026-11-23', year_b_partial: true })).toBe('Jan–Nov 2026')
    expect(yearBLabel({ year_b: '2026', year_b_through: '2026-01-09', year_b_partial: true })).toBe('Jan 2026')
    expect(yearBLabel({ year_b: '2026', year_b_through: null, year_b_partial: true })).toBe('2026 so far')
    expect(yearBLabel({ year_b: '2026', year_b_through: '2026-12-31', year_b_partial: false })).toBe('2026')
  })

  it('writes the change with its sign, a true minus, and no change for an empty base', () => {
    expect(changeLabel(relChange(10, 56))).toBe('+460%')
    expect(changeLabel(relChange(10, 8))).toBe('−20%')
    expect(changeLabel(relChange(10, 10))).toBe('0%')
    expect(changeLabel(relChange(0, 5))).toBe('—')
  })

  it('share is the default ranking: a growing recordings base does not fake growth', () => {
    // Meetings double but recordings double too: flat share, rising count.
    const flat = t('flat', 50, 100)
    const up = t('up', 10, 60)
    const down = t('down', 40, 40)
    const share = splitTopics([flat, down, up], 'share').rows.map((r) => [r.topic.slug, changeLabel(r.change)])
    expect(share).toEqual([
      ['up', '+200%'],
      ['flat', '0%'],
      ['down', '−50%'],
    ])
    const count = splitTopics([flat, down, up], 'count').rows.map((r) => [r.topic.slug, changeLabel(r.change)])
    expect(count[0]).toEqual(['up', '+500%'])
    expect(count[1]).toEqual(['flat', '+100%'])
  })

  it('supports sorting by most discussed in the latest year', () => {
    const smallFast = t('fast', 10, 60)
    const bigSteady = t('big', 200, 300)
    const sorted = splitTopics([smallFast, bigSteady], 'share', 'latest').rows.map((r) => r.topic.slug)
    expect(sorted).toEqual(['big', 'fast'])
  })

  it('filters between all topics, candidate topics without a story, and live stories', () => {
    const items = [t('guns', 10, 20, true, 1000, 2000, true, 100005), t('housing', 20, 40, true, 1000, 2000, false, 83)]
    expect(filterTopics(items, 'all').map((x) => x.slug)).toEqual(['guns', 'housing'])
    expect(filterTopics(items, 'candidates').map((x) => x.slug)).toEqual(['housing'])
    expect(filterTopics(items, 'stories').map((x) => x.slug)).toEqual(['guns'])
  })

  it('parses URL filter and sort params safely', () => {
    expect(parseTopicFilter('candidates')).toBe('candidates')
    expect(parseTopicFilter('stories')).toBe('stories')
    expect(parseTopicFilter('bogus')).toBe('all')
    expect(parseTopicFilter(null)).toBe('all')
    expect(parseYoySort('latest')).toBe('latest')
    expect(parseYoySort('change')).toBe('change')
    expect(parseYoySort(null)).toBe('change')
  })

  it('routes live stories to /stories/<slug> and candidate topics to /browse-topics?topic_id= keeping place', () => {
    const story = t('guns', 10, 20, true, 1000, 2000, true, 100005)
    const candidate = t('affordable-housing', 20, 40, true, 1000, 2000, false, 83)
    expect(topicDestination(story, 'GA', 'Atlanta')).toBe('/stories/guns?state=GA&city=Atlanta')
    expect(topicDestination(candidate, 'GA', 'Atlanta')).toBe('/browse-topics?topic_id=83&state=GA&city=Atlanta')
    expect(topicDestination(candidate, null, 'Atlanta')).toBe('/browse-topics?topic_id=83')
  })

  it('a topic the API cannot compare is listed, never drawn', () => {
    const { rows, tooFew } = splitTopics([t('ok', 10, 20), t('thin', 2, 40, false), t('none', 0, 0, false)], 'share')
    expect(rows.map((r) => r.topic.slug)).toEqual(['ok'])
    expect(tooFew.map((x) => x.slug)).toEqual(['none', 'thin'])
  })

  it('keeps the place in links, and a city only with its state', () => {
    expect(scopeQuery('GA', 'Atlanta')).toBe('?state=GA&city=Atlanta')
    expect(scopeQuery('GA', null)).toBe('?state=GA')
    expect(scopeQuery(null, 'Atlanta')).toBe('')
  })
})
