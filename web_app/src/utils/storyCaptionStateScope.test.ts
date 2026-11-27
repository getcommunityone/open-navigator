import { describe, expect, it } from 'vitest'
import type { TopicCaptionFacts } from '../api/topics'
import type { StoryScope } from './dataStory'
import { captionText, pickCaption } from './storyCaption'

// #1316 (owner, 27 Nov 2026): the step-up chain ends at the state. A state, or a place in it, never borrows America's title.
// Test stand-ins shaped like caption-facts; the Florida numbers mirror the owner's screenshot.
const fl: StoryScope = { stateCode: 'FL', stateName: 'Florida', city: null }
const miramar: StoryScope = { stateCode: 'FL', stateName: 'Florida', city: 'Miramar Beach' }
const nat: StoryScope = { stateName: null, city: null }
const usa = { level: 'national' as const, state_code: null, state: null, lean_meetings: 1216, public_against_meetings: 186, public_against_states: 30, public_for_meetings: 19, public_split_meetings: 29, public_silent_meetings: 982, disagreement_meetings: 4 }
const flWider = { level: 'state' as const, state_code: 'FL', state: 'Florida', lean_meetings: 40, public_against_meetings: 12, public_against_states: 1, public_for_meetings: 2, public_split_meetings: 1, public_silent_meetings: 25, disagreement_meetings: 0 }

function facts(scope: StoryScope, over: Partial<TopicCaptionFacts> = {}): TopicCaptionFacts {
  return {
    topic: 'license-plate-readers', topic_id: 1,
    scope: { level: scope.city ? 'city' : scope.stateCode ? 'state' : 'national', state_code: scope.stateCode ?? null, state: scope.stateName, city: scope.city },
    meetings: 9, states: [{ state_code: 'FL', state: 'Florida', meetings: 9, population: null }], top_state: 'FL', ratio_to_next: null,
    place: null, places: null, speakers: null,
    lean_meetings: 9, public_against_meetings: 2, public_for_meetings: 0, public_split_meetings: 0, public_silent_meetings: 7,
    disagreement_meetings: 0, disagreement_states: 0, wider: [usa], ...over,
  }
}
const text = (c: ReturnType<typeof pickCaption>) => captionText(c, 'Flock and license plate readers')

describe('a state-scoped story never shows America (#1316)', () => {
  it('Florida with too few meetings of its own: its own count title, not "America hates …"', () => {
    for (const slug of ['license-plate-readers', 'flock', 'pickleball', 'guns', 'short-term-rentals']) {
      const c = pickCaption(slug, facts(fl, { topic: slug }), fl)
      expect(captionText(c, 'x')).not.toMatch(/^America/)
      expect(c.widerPlace).toBeUndefined()
    }
    expect(text(pickCaption('license-plate-readers', facts(fl), fl))).toBe('Florida weighed Flock and license plate readers in 9 meetings.')
  })

  it('a city may step up to its state, never to the country', () => {
    const toState = pickCaption('license-plate-readers', facts(miramar, { meetings: 1, lean_meetings: 1, public_against_meetings: 0, public_silent_meetings: 1, wider: [flWider, usa] }), miramar)
    expect(toState.widerPlace).toBe('Florida')
    const thinState = { ...flWider, public_against_meetings: 1, public_for_meetings: 0, public_split_meetings: 0, public_silent_meetings: 39 }
    const neither = pickCaption('license-plate-readers', facts(miramar, { meetings: 1, lean_meetings: 1, public_against_meetings: 0, public_silent_meetings: 1, wider: [thinState, usa] }), miramar)
    expect(captionText(neither, 'x')).not.toMatch(/^America/)
  })

  it('nationally, America keeps its own conclusion', () => {
    const c = pickCaption('license-plate-readers', facts(nat, { meetings: 1300, lean_meetings: 1216, public_against_meetings: 186, public_for_meetings: 19, public_split_meetings: 29, public_silent_meetings: 982, wider: null }), nat)
    expect(text(c)).toMatch(/^America /)
  })
})
