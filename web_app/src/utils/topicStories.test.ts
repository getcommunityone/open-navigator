import { describe, expect, it } from 'vitest'
import type { TopicSummary } from '../api/topics'
import { GUIDE_DECOR, TILE_DECOR, buildTiles } from './homeTopicTiles'
import { CAPTION_COPY } from './storyCaption'
import { nextStoryLink } from './storyNav'
import { deriveTopicStories, isLiveTopic, liveStories, storyRoute } from './topicStories'

// Test stand-ins shaped like GET /api/topics rows, not warehouse figures.
const topic = (topic_id: number, query_id: string, name: string, meeting_count: number | null, source = 'curated'): TopicSummary => ({
  topic_id,
  name,
  query_id,
  keywords: [],
  transcript_occurrences: 0,
  source,
  meeting_count,
})

const CATALOG: TopicSummary[] = [
  topic(100001, 'data-centers', 'Data centers', 2257),
  topic(100003, 'short-term-rentals', 'Short-term rentals', 4186),
  topic(100004, 'license-plate-readers', 'Flock and license plate readers', 1235),
  topic(100005, 'guns', 'Guns', 7684),
  topic(100006, 'pickleball', 'Pickleball', 4014),
  topic(100009, 'animal-shelters', 'Animal shelters', 12),
  topic(100010, 'immigration', 'Immigration', 0),
  topic(57, 'bicycle-transportation', 'Bicycle transportation', 4482, 'civicsearch'),
]

describe('live topic rule', () => {
  it('a curated topic with meetings is live; zero, null or CivicSearch is not', () => {
    expect(isLiveTopic(CATALOG[1]!)).toBe(true)
    expect(isLiveTopic(CATALOG[6]!)).toBe(false)
    expect(isLiveTopic(topic(1, 'x', 'X', null))).toBe(false)
    expect(isLiveTopic(CATALOG[7]!)).toBe(false)
  })

  it('derives a topic story per live curated topic, data centers excluded (it stays on DataStory)', () => {
    const s = deriveTopicStories(CATALOG)
    expect(Object.keys(s).sort()).toEqual(['animal-shelters', 'guns', 'license-plate-readers', 'pickleball', 'short-term-rentals'])
    expect(s['short-term-rentals']!.companiesPath).toBe('/short-term-rentals/companies')
    expect(s['animal-shelters']).toMatchObject({ topicId: 100009, title: 'Animal shelters', meetings: 12 })
    expect(s['animal-shelters']!.lede).toContain('animal shelters')
    expect(deriveTopicStories(undefined)).toEqual({})
  })

  it('routes registry stories to DataStory and every other slug to TopicStory', () => {
    expect(storyRoute('data-centers')).toBe('data')
    expect(storyRoute('guns')).toBe('topic')
    expect(storyRoute('animal-shelters')).toBe('topic')
  })

  it('the next-story link walks the live stories in order', () => {
    const live = liveStories(deriveTopicStories(CATALOG))
    expect(live.map((l) => l.id)).toEqual(['data-centers', 'guns', 'short-term-rentals', 'pickleball', 'license-plate-readers', 'animal-shelters'])
    expect(nextStoryLink('data-centers', '?state=AL', live)).toMatchObject({ href: '/stories/guns?state=AL', label: 'Next story: Guns' })
    expect(nextStoryLink('animal-shelters', '', live)).toMatchObject({ href: '/stories', next: null })
  })
})

describe('home tiles', () => {
  it('tiles go live from the catalog; Flock and plate readers are one tile', () => {
    const tiles = buildTiles(CATALOG)
    const by = Object.fromEntries(tiles.map((t) => [t.key, t]))
    expect(by.dc).toMatchObject({ status: 'live', story: 'data-centers' })
    expect(by.str).toMatchObject({ status: 'live', story: 'short-term-rentals' })
    expect(by.lpr).toMatchObject({ status: 'live', story: 'license-plate-readers', title: 'Flock and license plate readers' })
    expect(tiles.filter((t) => t.story === 'license-plate-readers')).toHaveLength(1)
    expect(by.guns!.status).toBe('live')
    expect(by.pickleball!.status).toBe('live')
  })

  it('a topic with no curated meetings stays coming soon (bike lanes until #1131)', () => {
    const by = Object.fromEntries(buildTiles(CATALOG).map((t) => [t.key, t]))
    expect(by.bike).toMatchObject({ status: 'soon', story: undefined })
    expect(by.fluoride!.status).toBe('soon')
  })

  it('bike lanes goes live once a curated bike topic has meetings', () => {
    const by = Object.fromEntries(buildTiles([...CATALOG, topic(100011, 'bike-lanes', 'Bike lanes', 30)]).map((t) => [t.key, t]))
    expect(by.bike).toMatchObject({ status: 'live', story: 'bike-lanes' })
  })

  it('any other live curated topic gets its own tile; one with no meetings gets none', () => {
    const tiles = buildTiles(CATALOG)
    expect(tiles.find((t) => t.story === 'animal-shelters')).toMatchObject({ status: 'live', title: 'Animal shelters', captionKey: 'animal-shelters' })
    expect(tiles.find((t) => t.story === 'immigration')).toBeUndefined()
  })

  it('the nonprofit guide links to its page; insurance stays coming soon', () => {
    const by = Object.fromEntries(buildTiles(CATALOG).map((t) => [t.key, t]))
    expect(by.nonprofit).toMatchObject({ status: 'guide', guide: '/guides/starting-a-nonprofit' })
    expect(by.insurance).toMatchObject({ status: 'soon' })
    // Guides come last.
    expect(buildTiles(CATALOG).slice(-2).map((t) => t.key)).toEqual(['nonprofit', 'insurance'])
  })

  it('every known tile reads a caption key the picker knows, live or not (no fetch for a made-up slug)', () => {
    for (const d of [...TILE_DECOR, ...GUIDE_DECOR]) expect(CAPTION_COPY[d.caption ?? '']).toBeDefined()
  })

  it('before the catalog answers only data centers is live', () => {
    const tiles = buildTiles(undefined)
    expect(tiles.filter((t) => t.status === 'live').map((t) => t.key)).toEqual(['dc'])
  })
})
