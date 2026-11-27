import { describe, expect, it } from 'vitest'
import type { TopicCaptionFacts } from '../api/topics'
import type { StoryScope } from './dataStory'
import { CAPTION_COPY, DISAGREEMENT_MIN_MEETINGS, HATES_MIN_MEETINGS, captionSubhead, captionText, pickCaption, storyStartLabel, type Caption } from './storyCaption'

// Test stand-ins: shapes of the caption-facts response, not warehouse figures.
const nat: StoryScope = { stateName: null, city: null }
const ga: StoryScope = { stateCode: 'GA', stateName: 'Georgia', city: null }
const az: StoryScope = { stateCode: 'AZ', stateName: 'Arizona', city: null }
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
    topic: 'x',
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

const ZERO = /\b0 /

describe('pickCaption (a) hates', () => {
  it('nationally: confident public-against meetings at volume, plus the counted speakers', () => {
    const c = pickCaption(
      'data-centers',
      facts({ lean_meetings: 1828, public_against_meetings: 283, public_against_states: 32, disagreement_meetings: 23, disagreement_states: 10, speakers: { for: 3, against: 18, question: 1, neutral: 7, states: 4 } }),
      nat,
    )
    expect(c.kind).toBe('sentiment')
    expect(captionText(c, 'data centers')).toBe('America hates data centers.')
    expect(c.ai).toBe(true)
    expect(c.basis).toBe(
      "In 283 meetings across 32 states, the public mostly opposed data centers. 29 speakers counted by hand in 4 states: 18 against and 3 for.",
    )
  })

  it('uses the scope thresholds: 50 national, 10 state, 3 city', () => {
    expect(HATES_MIN_MEETINGS).toEqual({ national: 50, state: 10, city: 3 })
    expect(pickCaption('data-centers', facts({ public_against_meetings: 49 }), nat).kind).not.toBe('sentiment')
    const g = pickCaption('data-centers', facts({ public_against_meetings: 10, lean_meetings: 118 }, ga), ga)
    expect(captionText(g, 'data centers')).toBe('Georgia hates data centers.')
    const tus: StoryScope = { stateCode: 'AL', stateName: 'Alabama', city: 'Tuscaloosa' }
    const t = pickCaption('data-centers', facts({ public_against_meetings: 3 }, tus), tus)
    expect(captionText(t, 'data centers')).toBe('Tuscaloosa, Alabama hates data centers.')
    expect(pickCaption('data-centers', facts({ public_against_meetings: 2 }, tus), tus).kind).not.toBe('sentiment')
  })

  it('or the counted-speaker gate alone, never printing a zero side', () => {
    const c = pickCaption('data-centers', facts({ speakers: { for: 0, against: 11, question: 1, neutral: 0 } }, az), az)
    expect(captionText(c, 'data centers')).toBe('Arizona hates data centers.')
    expect(c.ai).toBe(false)
    expect(c.basis).toBe('12 speakers counted by hand in Arizona: 11 against.')
    expect(c.basis).not.toMatch(ZERO)
  })

  it('ignores the unreliable "for" readings; "hates" only for data centers, Flock / plate readers and pickleball', () => {
    expect(pickCaption('data-centers', facts({ public_for_meetings: 500 }), nat).kind).not.toBe('sentiment')
    expect(captionText(pickCaption('pickleball', facts({ public_against_meetings: 60 }), nat), 'pickleball')).toBe('America hates pickleball.')
  })
})

describe('pickCaption (b) divided', () => {
  it('officials sided against the public at volume (AI reading)', () => {
    const c = pickCaption('data-centers', facts({ lean_meetings: 1828, public_against_meetings: 20, disagreement_meetings: 23, disagreement_states: 10 }), nat)
    expect(c.kind).toBe('disagreement')
    expect(captionText(c, 'data centers')).toBe('America is divided on data centers.')
    expect(c.basis).toBe('In 23 meetings across 10 states, officials backed data centers while the public pushed back.')
    expect(c.ai).toBe(true)
  })

  it('in a state, and for a topic without a "hates" verb', () => {
    const c = pickCaption('guns', facts({ disagreement_meetings: 12, public_against_meetings: 40 }, ga), ga)
    expect(captionText(c, 'guns')).toBe('Georgia is divided on guns.')
    expect(c.basis).toBe('In 12 meetings in Georgia, officials sided against the public on gun control.')
  })

  it('or counted speakers split with both sides substantial', () => {
    const c = pickCaption('data-centers', facts({ speakers: { for: 14, against: 12, question: 0, neutral: 2 } }), nat)
    expect(captionText(c, 'data centers')).toBe('America is divided on data centers.')
    expect(c.basis).toBe('28 speakers counted by hand: 14 for and 12 against.')
  })

  it('falls through below the minimum', () => {
    expect(pickCaption('data-centers', facts({ disagreement_meetings: DISAGREEMENT_MIN_MEETINGS - 1 }), nat).kind).toBe('state_gap')
  })
})

describe('pickCaption (c) state gap', () => {
  it('national: the leading state by a clear ratio', () => {
    const c = pickCaption('short-term-rentals', facts(), nat)
    expect(c.place).toBe('California')
    expect(captionText(c, 'short-term rentals')).toBe('California took up short-term rentals in 570 meetings, more than any other state.')
    expect(c.basis).toContain('Then North Carolina, 317 meetings')
  })

  it('national: "more than twice" only at a ratio of 2 or more', () => {
    const states = [
      { state_code: 'CA', state: 'California', meetings: 228, population: null },
      { state_code: 'WA', state: 'Washington', meetings: 105, population: null },
    ]
    expect(captionText(pickCaption('license-plate-readers', facts({ states }), nat), 'Flock and license plate readers')).toBe(
      'California weighed Flock and license plate readers in 228 meetings, more than twice any other state.',
    )
  })

  it('national: a near tie names both states, and there is no per-resident claim', () => {
    const states = [
      { state_code: 'CA', state: 'California', meetings: 659, population: 39_000_000 },
      { state_code: 'NC', state: 'North Carolina', meetings: 585, population: 10_000_000 },
      { state_code: 'SD', state: 'South Dakota', meetings: 239, population: 900_000 },
    ]
    const c = pickCaption('guns', facts({ states }), nat)
    expect(captionText(c, 'gun control')).toBe('California and North Carolina took up gun control most: 659 and 585 meetings.')
    expect(c.basis).not.toContain('resident')
  })

  it('national: an exact tie reads "each"', () => {
    const states = [
      { state_code: 'MI', state: 'Michigan', meetings: 60, population: null },
      { state_code: 'WA', state: 'Washington', meetings: 60, population: null },
      { state_code: 'CA', state: 'California', meetings: 37, population: null },
    ]
    expect(captionText(pickCaption('water-fluoridation', facts({ states }), nat), 'water fluoridation')).toBe(
      'Michigan and Washington took up water fluoridation most: 60 meetings each.',
    )
  })

  it('state: the top state, and a ranked state', () => {
    const ca: StoryScope = { stateCode: 'CA', stateName: 'California', city: null }
    expect(captionText(pickCaption('short-term-rentals', facts({ meetings: 570 }, ca), ca), 'short-term rentals')).toBe(
      'California took up short-term rentals in 570 meetings, more than any other state.',
    )
    expect(captionText(pickCaption('short-term-rentals', facts({ meetings: 317 }, nc), nc), 'short-term rentals')).toBe(
      'North Carolina took up short-term rentals in 317 meetings, the 2nd most of any state.',
    )
    expect(captionText(pickCaption('short-term-rentals', facts({ meetings: 268 }, or), or), 'short-term rentals')).toBe(
      'Oregon took up short-term rentals in 268 meetings, the 3rd most of any state.',
    )
  })

  it('city: more than any other place in the state', () => {
    const places = [
      { name: 'Orlando', meetings: 13 },
      { name: 'Titusville', meetings: 9 },
    ]
    const c = pickCaption('short-term-rentals', facts({ meetings: 13, place: 'Orlando', places }, orl), orl)
    expect(captionText(c, 'short-term rentals')).toBe('Orlando, Florida took up short-term rentals in 13 meetings, more than any other place in Florida.')
  })
})

describe('pickCaption (d) volume and (e) question', () => {
  it('plain volume when no state difference stands out', () => {
    const c = pickCaption('short-term-rentals', facts({ meetings: 40 }, fl), fl)
    expect(c.kind).toBe('volume')
    expect(captionText(c, 'short-term rentals')).toBe('Florida took up short-term rentals in 40 meetings.')
  })

  it('the question with no meetings, no facts, or a guide', () => {
    expect(pickCaption('short-term-rentals', facts({ meetings: 0, states: [] }), nat).kind).toBe('question')
    expect(pickCaption('short-term-rentals', null, nat).kind).toBe('question')
    const guide = pickCaption('starting-a-nonprofit', facts(), fl)
    expect(captionText(guide, CAPTION_COPY['starting-a-nonprofit']!.topic)).toBe('What does it take to start a nonprofit in Florida?')
  })

  it('never uses facts for another scope than the one shown', () => {
    const c = pickCaption('data-centers', facts({ public_against_meetings: 37 }, ga), fl)
    expect(c.kind).toBe('question')
    expect(c.basis).toBeNull()
  })

  it('missing optional data falls through instead of reading as zero', () => {
    expect(pickCaption('data-centers', facts({ speakers: null, disagreement_meetings: null, public_against_meetings: null }), nat).kind).toBe('state_gap')
  })

  it('no caption or basis states a zero', () => {
    const cases: [string, TopicCaptionFacts, StoryScope][] = [
      ['data-centers', facts({ public_against_meetings: 283, disagreement_meetings: 0, speakers: { for: 0, against: 18, question: 0, neutral: 0 } }), nat],
      ['data-centers', facts({ disagreement_meetings: 11, disagreement_states: 0 }, ga), ga],
      ['data-centers', facts({ speakers: { for: 12, against: 12, question: 0, neutral: 0 } }), nat],
    ]
    for (const [k, f, s] of cases) {
      const c = pickCaption(k, f, s)
      expect(captionText(c, 'x')).not.toMatch(ZERO)
      expect(c.basis ?? '').not.toMatch(ZERO)
    }
  })
})

// #1134: the line under the caption speaks only for the caption's scope.
describe('captionSubhead', () => {
  const al = { stateCode: 'AL', stateName: 'Alabama', city: null }
  const tus = { stateCode: 'AL', stateName: 'Alabama', city: 'Tuscaloosa' }
  const cap = (kind: Caption['kind']): Caption => ({ kind, template: [], place: 'x', basis: null, ai: false })
  it("uses the story's national subhead only for the national sentiment", () => {
    expect(captionSubhead(cap('sentiment'), 'data-centers', { stateName: null, city: null })).toMatch(/^Public comments don't always match/)
    expect(captionSubhead(cap('sentiment'), 'data-centers', al)).toBe('At local meetings in Alabama, the public has mostly spoken against data centers.')
  })
  it('names the place for every other kind, and nothing for the question', () => {
    expect(captionSubhead(cap('volume'), 'data-centers', tus)).toBe('Where data centers came up at local meetings in Tuscaloosa, Alabama, in the words said there.')
    expect(captionSubhead(cap('disagreement'), 'data-centers', al)).toBe(
      "At local meetings in Alabama, the public and officials don't always land on the same side of data centers.",
    )
    expect(captionSubhead(cap('question'), 'data-centers', al)).toBeNull()
  })
})

describe('the title says what the map shows (#1182)', () => {
  const tus: StoryScope = { stateCode: 'AL', stateName: 'Alabama', city: 'Tuscaloosa' }
  const al: StoryScope = { stateCode: 'AL', stateName: 'Alabama', city: null }
  const NATIONAL_RED = { level: 'national' as const, state_code: null, state: null, lean_meetings: 1828, public_against_meetings: 283, public_against_states: 32, disagreement_meetings: 23 }
  const STATE_THIN = { level: 'state' as const, state_code: 'AL', state: 'Alabama', lean_meetings: 71, public_against_meetings: 6, public_against_states: 1, disagreement_meetings: 0 }
  const STATE_RED = { ...STATE_THIN, public_against_meetings: 12 }

  it('a national red map: "America hates data centers."', () => {
    const c = pickCaption('data-centers', facts({ lean_meetings: 1828, public_against_meetings: 283, public_against_states: 32 }), nat)
    expect(captionText(c, 'data centers')).toBe('America hates data centers.')
  })

  it('a city with thin readings in a red state names the state, never a bare city claim', () => {
    const c = pickCaption('data-centers', facts({ meetings: 2, lean_meetings: 2, public_against_meetings: 0, wider: [STATE_RED, NATIONAL_RED] }, tus), tus)
    expect(c.kind).toBe('wider_sentiment')
    expect(c.widerPlace).toBe('Alabama')
    expect(captionText(c, 'data centers')).toBe('Alabama hates data centers.')
    expect(c.ai).toBe(true)
    expect(c.basis).toBe(
      "Tuscaloosa, Alabama talked about data centers in 2 meetings. Of its 2 meetings read, none had a public mostly opposed. In 12 meetings in Alabama, the public mostly opposed data centers.",
    )
    expect(c.basis).not.toMatch(ZERO)
    // The place blank stays the scope's own place, so the label and the place picker still name Tuscaloosa.
    expect(c.place).toBe('Tuscaloosa, Alabama')
  })

  it('a thin state too: falls back to the country the map colours (Tuscaloosa, 26 Nov 2026 shape)', () => {
    const c = pickCaption('data-centers', facts({ meetings: 2, lean_meetings: 2, public_against_meetings: 0, wider: [STATE_THIN, NATIONAL_RED] }, tus), tus)
    expect(captionText(c, 'data centers')).toBe('America hates data centers.')
    expect(c.basis).toMatch(/^Tuscaloosa, Alabama talked about data centers in 2 meetings\. .*In 283 meetings across 32 states, /)
    // The line under the title starts with the place in scope (the home page draws it as the place control), no number.
    expect(captionSubhead(c, 'data-centers', tus)).toBe(
      "Tuscaloosa, Alabama hasn't had enough public comment on data centers to call. Showing America.",
    )
    const s = pickCaption('data-centers', facts({ meetings: 71, lean_meetings: 71, public_against_meetings: 6, wider: [NATIONAL_RED] }, al), al)
    expect(captionText(s, 'data centers')).toBe('America hates data centers.')
    expect(s.basis).toMatch(/^Alabama talked about data centers in 71 meetings\. .* In 283 meetings across 32 states, the public mostly opposed data centers\.$/)
    // Alabama has many readings, few against: the basis says so, never "too few readings".
    expect(s.basis).toMatch(/Of its 71 meetings read, 6 had a public mostly opposed, under the 10 a title of its own needs\./)
    const none = pickCaption('data-centers', facts({ meetings: 2, lean_meetings: null, public_against_meetings: null, wider: [NATIONAL_RED] }, tus), tus)
    expect(none.basis).toMatch(/^Tuscaloosa, Alabama talked about data centers in 2 meetings\. None has been read yet\./)
    // A state name missing from the API's broader entry comes from the scope, never a bare code.
    const unnamed = pickCaption('data-centers', facts({ meetings: 2, public_against_meetings: 0, wider: [{ ...STATE_RED, state: null }] }, tus), tus)
    expect(unnamed.widerPlace).toBe('Alabama')
    expect(unnamed.basis).toMatch(/In 12 meetings in Alabama, /)
  })

  it("the place's own reading still wins when it passes", () => {
    const c = pickCaption('data-centers', facts({ public_against_meetings: 3, wider: [STATE_RED, NATIONAL_RED] }, tus), tus)
    expect(captionText(c, 'data centers')).toBe('Tuscaloosa, Alabama hates data centers.')
  })

  it('no broader reading passes: the place keeps its own volume title', () => {
    const c = pickCaption('data-centers', facts({ meetings: 2, public_against_meetings: 0, wider: [STATE_THIN] }, tus), tus)
    expect(c.kind).toBe('volume')
  })

  it('a topic not allowed "hates" says plainly what the public mostly opposed (#1190)', () => {
    const c = pickCaption('water-fluoridation', facts({ lean_meetings: 526, public_against_meetings: 81, public_against_states: 19 }), nat)
    expect(captionText(c, 'water fluoridation')).toBe('America mostly opposes water fluoridation.')
    expect(captionText(c, 'water fluoridation')).not.toMatch(/hates|lean/)
    expect(c.basis).toBe("In 81 meetings across 19 states, the public mostly opposed water fluoridation.")
    const g = pickCaption('guns', facts({ public_against_meetings: 400 }), nat)
    expect(captionText(g, 'gun control')).toBe('America mostly opposes local gun-control measures.')
    expect(g.basis).toBe("In 400 meetings nationwide, the public mostly opposed local gun-control measures.")
    const az: StoryScope = { stateCode: 'AZ', stateName: 'Arizona', city: null }
    const r = pickCaption('short-term-rentals', facts({ public_against_meetings: 12 }, az), az)
    expect(captionText(r, 'short-term rentals')).toBe('Arizona mostly opposes short-term rentals.')
    const w = pickCaption('short-term-rentals', facts({ meetings: 40, public_against_meetings: 1, wider: [{ ...NATIONAL_RED, public_against_meetings: 60 }] }, fl), fl)
    expect(captionText(w, 'short-term rentals')).toBe('America mostly opposes short-term rentals.')
    expect(w.basis).toMatch(/^Florida took up short-term rentals in 40 meetings\. .*In 60 meetings .*, the public mostly opposed short-term rentals\.$/)
  })

  it('plain wording edge cases: one meeting, one state, and counted speakers alone never make a plain title (#1190)', () => {
    const tusc: StoryScope = { stateCode: 'AL', stateName: 'Alabama', city: 'Tuscaloosa' }
    const one = pickCaption('water-fluoridation', facts({ public_against_meetings: 3, lean_meetings: 4 }, tusc), tusc)
    expect(captionText(one, 'water fluoridation')).toBe('Tuscaloosa, Alabama mostly opposes water fluoridation.')
    const w = pickCaption('water-fluoridation', facts({ meetings: 1, lean_meetings: 1, public_against_meetings: 0, wider: [{ ...NATIONAL_RED, public_against_meetings: 50, public_against_states: 1 }] }, tusc), tusc)
    expect(captionText(w, 'water fluoridation')).toBe('America mostly opposes water fluoridation.')
    expect(w.basis).toBe(
      "Tuscaloosa, Alabama took up water fluoridation in 1 meeting. Of its 1 meeting read, none had a public mostly opposed. In 50 meetings nationwide, the public mostly opposed water fluoridation.",
    )
    const sp = pickCaption('water-fluoridation', facts({ meetings: 30, public_against_meetings: 2, speakers: { for: 1, against: 40, question: 0, neutral: 0, states: 3 } }), nat)
    expect(sp.kind).not.toBe('sentiment')
  })
})

describe('storyStartLabel (#1182)', () => {
  it('names the topic, and the place unless national', () => {
    expect(storyStartLabel('data-centers', 'Tuscaloosa, Alabama')).toBe('Start the data center story for Tuscaloosa, Alabama')
    expect(storyStartLabel('license-plate-readers', 'National')).toBe('Start the Flock and license plate readers story')
    expect(storyStartLabel('homelessness', 'Georgia', 'Homelessness and shelters')).toBe('Start the homelessness and shelters story for Georgia')
  })
})

describe('no "AI reading" in caption copy (#1222, owner 2026-11-26)', () => {
  it('titles, bases and subheads never say "AI reading"', () => {
    const scopes: StoryScope[] = [{ stateName: null, city: null }, { stateCode: 'AL', stateName: 'Alabama', city: null }, { stateCode: 'AL', stateName: 'Alabama', city: 'Tuscaloosa' }]
    const shapes = [
      { lean_meetings: 1828, public_against_meetings: 283, public_against_states: 32, disagreement_meetings: 23, disagreement_states: 10 },
      { lean_meetings: 1828, public_against_meetings: 20, disagreement_meetings: 23, disagreement_states: 10 },
    ]
    for (const sc of scopes) for (const f of shapes) for (const k of ['data-centers', 'guns', 'water-fluoridation']) {
      const c = pickCaption(k, facts(f, sc), sc)
      for (const line of [captionText(c, k), c.basis ?? '', captionSubhead(c, k, sc) ?? '']) expect(line).not.toMatch(/AI read/)
    }
  })
})
