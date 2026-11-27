import { describe, expect, it } from 'vitest'
import type { TopicCaptionFacts } from '../api/topics'
import type { StoryScope } from './dataStory'
import { captionSubhead, captionText, pickCaption } from './storyCaption'

// Test stand-ins: shapes of the caption-facts response (#1200), not warehouse figures.
const nat: StoryScope = { stateName: null, city: null }
const oh: StoryScope = { stateCode: 'OH', stateName: 'Ohio', city: null }
const tus: StoryScope = { stateCode: 'AL', stateName: 'Alabama', city: 'Tuscaloosa' }

function facts(lean: { against: number; for: number; split: number; silent: number } | null, scope: StoryScope = nat, over: Partial<TopicCaptionFacts> = {}): TopicCaptionFacts {
  return {
    topic: 'x',
    topic_id: 1,
    scope: { level: scope.city ? 'city' : scope.stateCode ? 'state' : 'national', state_code: scope.stateCode ?? null, state: scope.stateName, city: scope.city },
    meetings: 700,
    states: [
      { state_code: 'CA', state: 'California', meetings: 659, population: null },
      { state_code: 'NC', state: 'North Carolina', meetings: 585, population: null },
      { state_code: 'OH', state: 'Ohio', meetings: 63, population: null },
    ],
    top_state: 'CA',
    ratio_to_next: 1.1,
    place: null,
    places: null,
    speakers: null,
    lean_meetings: lean ? lean.against + lean.for + lean.split + lean.silent : null,
    public_against_meetings: lean ? lean.against : null,
    public_for_meetings: lean ? lean.for : null,
    public_split_meetings: lean ? lean.split : null,
    public_silent_meetings: lean ? lean.silent : null,
    disagreement_meetings: 0,
    disagreement_states: 0,
    ...over,
  }
}
const text = (slug: string, f: TopicCaptionFacts, s: StoryScope, topic: string) => captionText(pickCaption(slug, f, s), topic)

describe('pickCaption (p) position, in the topic words (#1200)', () => {
  it('a state majority states the side in the topic words with the count', () => {
    const c = pickCaption('guns', facts({ against: 10, for: 41, split: 12, silent: 0 }, oh), oh)
    expect(c.kind).toBe('position')
    expect(c.ai).toBe(true)
    expect(captionText(c, 'guns')).toBe('In Ohio, most meetings that took up guns backed the gun proposal before them: 41 of 63 where the public spoke (AI reading).')
    expect(captionText(c, 'guns')).not.toMatch(/limit/)
  })

  it('national majority for short-term rentals: wanted limits (topic_lean: against = restricting)', () => {
    const c = pickCaption('short-term-rentals', facts({ against: 304, for: 102, split: 30, silent: 2444 }), nat)
    expect(captionText(c, 'short-term rentals')).toBe(
      'Across America, most meetings that took up short-term rentals wanted limits on short-term rentals: 304 of 436 where the public spoke (AI reading).',
    )
    expect(c.basis).toMatch(/^AI reading of each meeting's transcript: of 2,880 meetings read nationwide, the public spoke in 436/)
    expect(c.basis).toMatch(/In 2,444 it didn't speak on it\./)
    expect(captionSubhead(c, 'short-term-rentals', nat)).toMatch(/as an AI read each meeting's transcript/)
  })

  it('"hates" only for its topics, and only for a majority against', () => {
    expect(text('pickleball', facts({ against: 40, for: 5, split: 5, silent: 0 }), nat, 'pickleball')).toBe(
      'America hates pickleball: the public was against it in 40 of 50 meetings where it spoke (AI reading).',
    )
    expect(text('pickleball', facts({ against: 5, for: 191, split: 10, silent: 3681 }), nat, 'pickleball')).toMatch(
      /^Across America, most meetings that took up pickleball wanted the pickleball courts: 191 of 206/,
    )
    expect(text('water-fluoridation', facts({ against: 40, for: 5, split: 5, silent: 0 }), nat, 'water fluoridation')).not.toMatch(/hates/)
  })

  it('no side with a majority: "is split on"', () => {
    const c = pickCaption('license-plate-readers', facts({ against: 6, for: 5, split: 2, silent: 30 }, oh), oh)
    expect(c.verdict).toBe('split')
    expect(captionText(c, 'Flock and license plate readers')).toBe(
      'Ohio is split on Flock and license plate readers (AI reading of 13 meetings where the public spoke).',
    )
  })

  it('too few: keeps the count title and says how many meetings have a reading so far', () => {
    const c = pickCaption('guns', facts({ against: 0, for: 1, split: 0, silent: 19 }), nat)
    expect(c.kind).toBe('state_gap')
    expect(captionText(c, 'guns')).toBe('California and North Carolina took up guns most: 659 and 585 meetings.')
    expect(c.basis).toMatch(/20 of 700 meetings have an AI reading so far; the public spoke on guns in 1, too few for a conclusion\.$/)
  })

  it('readings in labels outside the question are said, never counted as a side (#1204)', () => {
    const f = facts({ against: 0, for: 0, split: 0, silent: 413 }, nat, { meetings: 526, lean_meetings: 526 })
    const c = pickCaption('water-fluoridation', f, nat)
    expect(c.kind).not.toBe('position')
    expect(c.basis).toMatch(/413 of 526 meetings have an AI reading so far; in all of them the public didn't speak on water fluoridation\. 113 meetings more have a reading in labels this page can't show yet\.$/)
  })

  it('no reading at all: says so under the count title', () => {
    const c = pickCaption('guns', facts({ against: 0, for: 0, split: 0, silent: 0 }, oh), oh)
    expect(c.basis).toMatch(/No meeting in Ohio has an AI reading of the public's position yet\./)
  })

  it('a city too thin of its own names the broader scope with a conclusion', () => {
    const f = facts({ against: 0, for: 1, split: 0, silent: 1 }, tus, {
      meetings: 2,
      wider: [
        { level: 'state', state_code: 'AL', state: 'Alabama', lean_meetings: 4, public_against_meetings: 1, public_against_states: 1, public_for_meetings: 1, public_split_meetings: 0, public_silent_meetings: 2, disagreement_meetings: 0 },
        { level: 'national', state_code: null, state: null, lean_meetings: 900, public_against_meetings: 300, public_against_states: 30, public_for_meetings: 20, public_split_meetings: 20, public_silent_meetings: 560, disagreement_meetings: 0 },
      ],
    })
    const c = pickCaption('data-centers', f, tus)
    expect(c.kind).toBe('wider_position')
    expect(captionText(c, 'data centers')).toBe(
      'America hates data centers: the public was against them in 300 of 340 meetings where it spoke (AI reading); Tuscaloosa, Alabama brought them up in 2 meetings.',
    )
  })

  it('an older API without split and silent keeps the earlier rules and adds no note', () => {
    const f = facts(null)
    delete (f as Partial<TopicCaptionFacts>).public_split_meetings
    delete (f as Partial<TopicCaptionFacts>).public_silent_meetings
    const c = pickCaption('guns', f, nat)
    expect(c.kind).toBe('state_gap')
    expect(c.basis).not.toMatch(/AI reading/)
  })
})
