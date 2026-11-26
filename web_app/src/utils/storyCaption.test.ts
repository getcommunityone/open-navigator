import { describe, expect, it } from 'vitest'
import type { TopicCaptionFacts } from '../api/topics'
import type { StoryScope } from './dataStory'
import {
  CAPTION_COPY,
  DISAGREEMENT_MIN_MEETINGS,
  PUBLIC_LEAN_MIN_MEETINGS,
  captionText,
  pickCaption,
} from './storyCaption'

// Test stand-ins: shapes of the caption-facts response, not warehouse figures.
const nat: StoryScope = { stateName: null, city: null }
const ga: StoryScope = { stateCode: 'GA', stateName: 'Georgia', city: null }
const nc: StoryScope = { stateCode: 'NC', stateName: 'North Carolina', city: null }
const or: StoryScope = { stateCode: 'OR', stateName: 'Oregon', city: null }
const fl: StoryScope = { stateCode: 'FL', stateName: 'Florida', city: null }
const orl: StoryScope = { stateCode: 'FL', stateName: 'Florida', city: 'Orlando' }

const STATES = [
  { state_code: 'CA', state: 'California', meetings: 570, population: 39_000_000 },
  { state_code: 'NC', state: 'North Carolina', meetings: 317, population: 10_000_000 },
  { state_code: 'OR', state: 'Oregon', meetings: 268, population: 4_000_000 },
  { state_code: 'TN', state: 'Tennessee', meetings: 250, population: 7_000_000 },
  { state_code: 'FL', state: 'Florida', meetings: 40, population: 21_000_000 },
]

function facts(over: Partial<TopicCaptionFacts> = {}, scope: StoryScope = nat): TopicCaptionFacts {
  return {
    topic: 'short-term-rentals',
    topic_id: 1,
    scope: {
      level: scope.city ? 'city' : scope.stateCode ? 'state' : 'national',
      state_code: scope.stateCode ?? null,
      state: scope.stateName,
      city: scope.city,
    },
    meetings: 1000,
    states: STATES,
    top_state: 'CA',
    ratio_to_next: 1.8,
    place: null,
    places: null,
    speakers: null,
    lean_meetings: null,
    public_against_meetings: null,
    public_for_meetings: null,
    disagreement_meetings: null,
    disagreement_states: null,
    ...over,
  }
}

describe('pickCaption', () => {
  it('rule 1: officials sided against the public at volume, labelled as an AI reading', () => {
    const c = pickCaption('data-centers', facts({ lean_meetings: 1800, public_against_meetings: 280, disagreement_meetings: 23, disagreement_states: 10 }), nat)
    expect(c.kind).toBe('disagreement')
    expect(c.ai).toBe(true)
    expect(captionText(c, 'data centers')).toBe('In 23 meetings across America, officials backed data centers while the public pushed back.')
    expect(c.basis).toContain('Jev (an AI classifier) read the transcripts of 1,800 meetings nationwide: the public leaned against in 280; officials sided against the public in 23, in 10 states.')
  })

  it('rule 1: a for/against speaker split where both sides are substantial', () => {
    const c = pickCaption('data-centers', facts({ speakers: { for: 14, against: 12, question: 1, neutral: 2 } }), nat)
    expect(c.kind).toBe('disagreement')
    expect(c.ai).toBe(false)
    expect(captionText(c, 'data centers')).toBe('America is split on data centers: 14 spoke for, 12 against.')
  })

  it('rule 1 falls through below the disagreement minimum', () => {
    const c = pickCaption('data-centers', facts({ lean_meetings: 100, public_against_meetings: 5, disagreement_meetings: DISAGREEMENT_MIN_MEETINGS - 1 }), nat)
    expect(c.kind).not.toBe('disagreement')
  })

  it('rule 2: the existing speaker gate keeps "America hates data centers."', () => {
    const c = pickCaption('data-centers', facts({ speakers: { for: 3, against: 18, question: 1, neutral: 7 } }), nat)
    expect(c.kind).toBe('sentiment')
    expect(captionText(c, 'data centers')).toBe('America hates data centers.')
    expect(c.basis).toBe('Of 29 speakers on record at local meetings, 18 spoke against and 3 spoke for.')
  })

  it('rule 2: the public lean (AI reading) at volume for a state', () => {
    const c = pickCaption('data-centers', facts({ lean_meetings: 118, public_against_meetings: 37, disagreement_meetings: 0 }, ga), ga)
    expect(c.kind).toBe('sentiment')
    expect(c.ai).toBe(true)
    expect(captionText(c, 'data centers')).toBe('The public pushed back on data centers in 37 meetings in Georgia.')
    expect(c.basis).toContain('(31%)')
  })

  it('rule 2: the public lean needs its minimum count and share', () => {
    const few = pickCaption('data-centers', facts({ lean_meetings: 40, public_against_meetings: PUBLIC_LEAN_MIN_MEETINGS - 1 }, ga), ga)
    expect(few.kind).not.toBe('sentiment')
    const thin = pickCaption('data-centers', facts({ lean_meetings: 1000, public_against_meetings: 30 }, ga), ga)
    expect(thin.kind).not.toBe('sentiment')
  })

  it('rule 3 national: the leading state by a clear ratio names the state', () => {
    const c = pickCaption('short-term-rentals', facts(), nat)
    expect(c.kind).toBe('state_gap')
    expect(c.place).toBe('California')
    expect(captionText(c, 'short-term rentals')).toBe('California took up short-term rentals in 570 meetings, more than any other state.')
    expect(c.basis).toContain('Next: North Carolina, 317 meetings')
  })

  it('rule 3 national: "more than twice" only when the ratio is at least 2', () => {
    const states = [
      { state_code: 'CA', state: 'California', meetings: 228, population: null },
      { state_code: 'WA', state: 'Washington', meetings: 105, population: null },
    ]
    const c = pickCaption('license-plate-readers', facts({ states }), nat)
    expect(captionText(c, 'license plate readers')).toBe('California weighed license plate readers in 228 meetings, more than twice any other state.')
  })

  it('rule 3 national: per resident when the raw lead is close and population is on record', () => {
    const states = [
      { state_code: 'CA', state: 'California', meetings: 659, population: 39_000_000 },
      { state_code: 'NC', state: 'North Carolina', meetings: 585, population: 10_000_000 },
      { state_code: 'SD', state: 'South Dakota', meetings: 239, population: 900_000 },
    ]
    const c = pickCaption('guns', facts({ states }), nat)
    expect(c.kind).toBe('state_gap')
    expect(captionText(c, 'guns')).toBe('South Dakota took up guns in 239 meetings, the most per resident of any state.')
    expect(c.basis).toContain('per million residents')
  })

  it('rule 3 national: no per-resident claim without population on record', () => {
    const states = STATES.map((s) => ({ ...s, population: null })).map((s, i) => (i === 0 ? { ...s, meetings: 330 } : s))
    const c = pickCaption('short-term-rentals', facts({ states }), nat)
    expect(c.kind).toBe('volume')
  })

  it('rule 3 state: the top state, and a ranked state', () => {
    const ca = pickCaption('short-term-rentals', facts({ meetings: 570 }, { stateCode: 'CA', stateName: 'California', city: null }), { stateCode: 'CA', stateName: 'California', city: null })
    expect(captionText(ca, 'short-term rentals')).toBe('California took up short-term rentals in 570 meetings, more than any other state.')
    const second = pickCaption('short-term-rentals', facts({ meetings: 317 }, nc), nc)
    expect(captionText(second, 'short-term rentals')).toBe('North Carolina took up short-term rentals in 317 meetings, the 2nd most of any state.')
    // Oregon leads per resident (268 per 4M), which outranks its 3rd place by raw count.
    const perRes = pickCaption('short-term-rentals', facts({ meetings: 268 }, or), or)
    expect(captionText(perRes, 'short-term rentals')).toBe('Oregon took up short-term rentals in 268 meetings, the most per resident of any state.')
    const noPop = STATES.map((s) => ({ ...s, population: null }))
    const third = pickCaption('short-term-rentals', facts({ meetings: 268, states: noPop }, or), or)
    expect(captionText(third, 'short-term rentals')).toBe('Oregon took up short-term rentals in 268 meetings, the 3rd most of any state.')
  })

  it('rule 3 city: more than any other place in the state', () => {
    const places = [
      { name: 'Orlando', meetings: 13 },
      { name: 'Titusville', meetings: 9 },
    ]
    const c = pickCaption('short-term-rentals', facts({ meetings: 13, place: 'Orlando', places }, orl), orl)
    expect(captionText(c, 'short-term rentals')).toBe('Orlando, Florida took up short-term rentals in 13 meetings, more than any other place in Florida.')
  })

  it('rule 4: plain volume when no state difference stands out', () => {
    const c = pickCaption('short-term-rentals', facts({ meetings: 40 }, fl), fl)
    expect(c.kind).toBe('volume')
    expect(captionText(c, 'short-term rentals')).toBe('Florida took up short-term rentals in 40 meetings.')
  })

  it('rule 5: the question with no meetings, no facts, or a guide', () => {
    expect(pickCaption('short-term-rentals', facts({ meetings: 0, states: [] }), nat).kind).toBe('question')
    expect(pickCaption('short-term-rentals', null, nat).kind).toBe('question')
    const guide = pickCaption('starting-a-nonprofit', facts(), fl)
    expect(guide.kind).toBe('question')
    expect(captionText(guide, CAPTION_COPY['starting-a-nonprofit']!.topic)).toBe('What does it take to start a nonprofit in Florida?')
  })

  it('never uses facts for another scope than the one shown', () => {
    // Facts for Georgia under a Florida label: the caption must not borrow them.
    const c = pickCaption('data-centers', facts({ lean_meetings: 118, public_against_meetings: 37 }, ga), fl)
    expect(c.kind).toBe('question')
    expect(c.basis).toBeNull()
  })

  it('missing optional data falls through instead of reading as zero', () => {
    const c = pickCaption('data-centers', facts({ speakers: null, disagreement_meetings: null, public_against_meetings: null }), nat)
    expect(c.kind).toBe('state_gap')
  })
})
