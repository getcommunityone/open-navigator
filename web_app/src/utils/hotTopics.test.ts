import { describe, expect, it } from 'vitest'
import type { YoyResponse, YoyTopic } from '../api/topicsYoy'
import { buildHotPills, pillBadgeText, topicHeated, topicRise } from './hotTopics'

const topic = (o: Partial<YoyTopic> & { slug: string }): YoyTopic => ({
  topic_id: 1, name: o.slug, source: 'civicsearch', has_story: false, year_a: '2025', year_b: '2026',
  meetings_a: 10, meetings_b: 10, recorded_a: 100, recorded_b: 100, share_a: 0.1, share_b: 0.1, comparable: true,
  heat_rated: 0, heat_mean: null, ...o,
})
const yoy = (topics: YoyTopic[]): YoyResponse => ({
  scope: { level: 'national', state_code: null, state: null, city: null }, year_a: '2025', year_b: '2026', year_b_through: null,
  year_b_partial: true, recorded_a: 100, recorded_b: 100, thin_year: null, min_meetings: 5, min_recorded_meetings: 20, min_heat_rated: 20, topics,
})
const live = [{ id: 'data-centers', title: 'Data centers' }, { id: 'guns', title: 'Gun control' }]

describe('topicRise / topicHeated', () => {
  it('needs comparable and a 25% share rise', () => {
    expect(topicRise(topic({ slug: 'a', share_a: 0.1, share_b: 0.2 }))).toBeCloseTo(1)
    expect(topicRise(topic({ slug: 'a', share_a: 0.1, share_b: 0.12 }))).toBeNull()
    expect(topicRise(topic({ slug: 'a', share_a: 0.1, share_b: 0.3, comparable: false }))).toBeNull()
    expect(topicRise(topic({ slug: 'a', share_a: 0, share_b: 0.3 }))).toBeNull()
  })
  it('heated only with a mean from the API at or above 3', () => {
    expect(topicHeated(topic({ slug: 'a', heat_mean: 3.7 }))).toBe(3.7)
    expect(topicHeated(topic({ slug: 'a', heat_mean: 2.04 }))).toBeNull()
    expect(topicHeated(topic({ slug: 'a', heat_mean: null }))).toBeNull()
  })
})

describe('buildHotPills', () => {
  it('is just the live stories, in catalog order, with no yoy data', () => {
    const p = buildHotPills(live, undefined)
    expect(p.map((x) => x.id)).toEqual(['data-centers', 'guns'])
    expect(p.every((x) => x.live && x.score === 0 && x.rise == null && x.heat == null)).toBe(true)
  })
  it('adds rising and heated topics, ordered by combined score, live marked', () => {
    const p = buildHotPills(live, yoy([
      topic({ slug: 'data-centers', topic_id: 7, share_a: 0.04, share_b: 0.08, heat_mean: 3.71, heat_rated: 1100, has_story: true }),
      topic({ slug: 'guns', topic_id: 8, share_a: 0.09, share_b: 0.057 }),
      topic({ slug: 'building-setbacks', topic_id: 9, share_a: 0.01, share_b: 0.03 }),
      topic({ slug: 'immigration', topic_id: 10, heat_mean: 4.01, heat_rated: 91 }),
      topic({ slug: 'flat', topic_id: 11 }),
    ]))
    expect(p.map((x) => x.id)).toEqual(['data-centers', 'immigration', 'building-setbacks', 'guns'])
    expect(p[0]).toMatchObject({ live: true, topicId: 7 })
    expect(p[0]!.rise).toBeCloseTo(1)
    expect(p[0]!.heat).toBe(3.71)
    expect(p[2]).toMatchObject({ live: false, heat: null })
    expect(p[1]).toMatchObject({ live: false, rise: null, heat: 4.01, heatRated: 91 })
    expect(p.find((x) => x.id === 'flat')).toBeUndefined()
  })
  it('caps the rising and heated sets and sorts by score', () => {
    const many = Array.from({ length: 20 }, (_, i) => topic({ slug: `t${i}`, topic_id: i, share_a: 0.1, share_b: 0.1 * (1.3 + i * 0.05) }))
    const p = buildHotPills([], yoy(many))
    expect(p).toHaveLength(8)
    expect(p[0]!.id).toBe('t19')
    expect(p.map((x) => x.score)).toEqual([...p.map((x) => x.score)].sort((a, b) => b - a))
  })
  it('recomputes per scope: a different yoy gives a different row', () => {
    const nat = buildHotPills(live, yoy([topic({ slug: 'a', share_a: 0.1, share_b: 0.3 })]))
    const ga = buildHotPills(live, yoy([topic({ slug: 'b', share_a: 0.1, share_b: 0.3 })]))
    expect(nat.map((x) => x.id)).toContain('a')
    expect(ga.map((x) => x.id)).not.toContain('a')
    expect(ga.map((x) => x.id)).toContain('b')
  })
})

describe('pillBadgeText', () => {
  it('states only what is real', () => {
    expect(pillBadgeText({ rise: null, heat: null, heatRated: 0 })).toBe('')
    expect(pillBadgeText({ rise: 0.62, heat: 3.7, heatRated: 1100 })).toContain('up 62%')
    expect(pillBadgeText({ rise: 0.62, heat: 3.7, heatRated: 1100 })).toContain('3.7 of 5 (1,100 rated)')
  })
})
