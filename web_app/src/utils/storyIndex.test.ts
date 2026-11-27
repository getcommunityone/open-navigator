import { describe, expect, it } from 'vitest'
import type { TopicCaptionFacts, TopicSummary } from '../api/topics'
import { STORIES } from './dataStory'
import { storyCardMeetings, storyCardTitle, storyFactsSlug, storyIndexCards } from './storyIndex'

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
  topic(100009, 'animal-shelters', 'Animal shelters', 12),
  topic(100003, 'short-term-rentals', 'Short-term rentals', 4186),
  topic(100001, 'data-centers', 'Data centers', 2257),
  topic(100005, 'guns', 'Guns', 7684),
  topic(100004, 'license-plate-readers', 'Flock and license plate readers', 1235),
  topic(100006, 'pickleball', 'Pickleball', 4014),
  topic(100011, 'traffic-safety', 'Traffic safety', 900),
  topic(100010, 'immigration', 'Immigration', 0),
  topic(57, 'bicycle-transportation', 'Bicycle transportation', 4482, 'civicsearch'),
]

const NATIONAL = { stateCode: undefined, stateName: null, city: null }
const ALABAMA = { stateCode: 'AL', stateName: 'Alabama', city: null }

describe('storyIndexCards', () => {
  it('lists data centers first, then the home strip order, then other live topics by meetings', () => {
    const cards = storyIndexCards(CATALOG)
    expect(cards.map((c) => c.key)).toEqual([
      'dc',
      'str',
      'lpr',
      'guns',
      'pickleball',
      'bike',
      'fluoride',
      'topic-traffic-safety',
      'topic-animal-shelters',
    ])
    // The guns card is named "Gun control" (#1237), whatever the catalog calls it.
    expect(cards.find((c) => c.key === 'guns')!.title).toBe('Gun control')
  })

  it('splits live stories from coming soon: no meetings or no curated topic means no story link', () => {
    const cards = storyIndexCards(CATALOG)
    const live = cards.filter((c) => c.status === 'live').map((c) => c.story)
    expect(live).toEqual(['data-centers', 'short-term-rentals', 'license-plate-readers', 'guns', 'pickleball', 'traffic-safety', 'animal-shelters'])
    const soon = cards.filter((c) => c.status === 'soon')
    expect(soon.map((c) => c.key)).toEqual(['bike', 'fluoride'])
    expect(soon.every((c) => c.story === undefined)).toBe(true)
  })

  it('leaves the guides out (they are not meeting stories)', () => {
    const keys = storyIndexCards(CATALOG).map((c) => c.key)
    expect(keys).not.toContain('nonprofit')
    expect(keys).not.toContain('insurance')
  })

  it('with no catalog keeps data centers live (a registry story)', () => {
    const cards = storyIndexCards(undefined)
    expect(cards[0]).toMatchObject({ key: 'dc', status: 'live', story: 'data-centers' })
    expect(cards.slice(1).every((c) => c.status === 'soon')).toBe(true)
  })
})

describe('card title and meetings', () => {
  const dc = storyIndexCards(CATALOG)[0]!
  const facts = (over: Partial<TopicCaptionFacts>): TopicCaptionFacts => ({
    topic: 'data-centers',
    topic_id: 100001,
    scope: { level: 'state', state_code: 'AL', state: 'Alabama', city: null },
    meetings: 93,
    states: [],
    top_state: null,
    ratio_to_next: null,
    place: null,
    places: null,
    speakers: null,
    lean_meetings: null,
    public_against_meetings: null,
    public_for_meetings: null,
    disagreement_meetings: null,
    disagreement_states: null,
    ...over,
  })

  it('reads the facts slug the home strip reads', () => {
    expect(storyFactsSlug(dc)).toBe('data-centers')
  })

  it('asks the registry story question while there are no facts', () => {
    expect(storyCardTitle(dc, undefined, NATIONAL)).toBe(STORIES['data-centers']!.question)
  })

  it('takes the meetings for the scope asked, never a stale scope', () => {
    expect(storyCardMeetings(facts({}), ALABAMA)).toBe(93)
    expect(storyCardMeetings(facts({}), NATIONAL)).toBeNull()
    expect(storyCardMeetings(facts({ meetings: 0 }), ALABAMA)).toBeNull()
    expect(storyCardMeetings(facts({ meetings: null }), ALABAMA)).toBeNull()
  })

  it('titles a scoped card with its place', () => {
    expect(storyCardTitle(dc, facts({}), ALABAMA)).toMatch(/Alabama/)
  })
})
