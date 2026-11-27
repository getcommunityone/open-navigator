import { describe, expect, it } from 'vitest'
import { changeLabel, relChange, scopeQuery, splitTopics, yearBLabel } from './topicsYoy'
import type { YoyTopic } from '../api/topicsYoy'

// Test-only rows: nothing here is served by the app.
const t = (slug: string, ma: number, mb: number, comparable = true, ra = 1000, rb = 2000): YoyTopic => ({
  topic_id: 1,
  slug,
  name: slug,
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

describe('Browse all topics (#1343)', () => {
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
