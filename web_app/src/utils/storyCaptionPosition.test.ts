import { describe, expect, it } from 'vitest'
import type { TopicCaptionFacts } from '../api/topics'
import type { StoryScope } from './dataStory'
import { captionSubhead, captionText, pickCaption, withTopicBlank } from './storyCaption'

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
    expect(captionText(c, 'gun control')).toBe('Ohio mostly favors gun limits.')
    expect(c.basis).toMatch(/^Most meetings favored gun limits: 41 of 63 where the public spoke\. /)
    expect(captionText(c, 'gun control')).not.toMatch(/proposal/)
  })

  it('national majority for short-term rentals: wanted limits (topic_lean: against = restricting)', () => {
    const c = pickCaption('short-term-rentals', facts({ against: 304, for: 102, split: 30, silent: 2444 }), nat)
    expect(captionText(c, 'short-term rentals')).toBe(
      'America mostly wants limits on short-term rentals.',
    )
    expect(c.basis).toMatch(/^Most meetings wanted limits on short-term rentals: 304 of 436 where the public spoke\. Of 2,880 meetings read nationwide, the public spoke in 436/)
    expect(c.basis).toMatch(/In 2,444 it didn't speak on it\./)
    expect(captionSubhead(c, 'short-term-rentals', nat)).toMatch(/read from each meeting's transcript/)
  })

  it('"hates" only for its topics, and only for a majority against', () => {
    expect(text('pickleball', facts({ against: 40, for: 5, split: 5, silent: 0 }), nat, 'pickleball')).toBe(
      'America hates pickleball.',
    )
    expect(text('pickleball', facts({ against: 5, for: 191, split: 10, silent: 3681 }), nat, 'pickleball')).toMatch(
      /^America mostly wants the pickleball courts\.$/,
    )
    expect(text('water-fluoridation', facts({ against: 40, for: 5, split: 5, silent: 0 }), nat, 'water fluoridation')).not.toMatch(/hates/)
  })

  it('no side with a majority: "is split on"', () => {
    const c = pickCaption('license-plate-readers', facts({ against: 6, for: 5, split: 2, silent: 30 }, oh), oh)
    expect(c.verdict).toBe('split')
    expect(captionText(c, 'Flock and license plate readers')).toBe(
      'Ohio is split on Flock and license plate readers.',
    )
    expect(c.basis).toMatch(/^The public was split on Flock and license plate readers in the 13 meetings where it spoke\. /)
  })

  it('too few: keeps the count title and says how many meetings have a reading so far', () => {
    const c = pickCaption('guns', facts({ against: 0, for: 1, split: 0, silent: 19 }), nat)
    expect(c.kind).toBe('state_gap')
    expect(captionText(c, 'gun control')).toBe('California and North Carolina took up gun control most: 659 and 585 meetings.')
    expect(c.basis).toMatch(/20 of 700 meetings have a reading so far; the public spoke on gun control in 1, too few for a conclusion\.$/)
  })

  it('readings in labels outside the question are said, never counted as a side (#1204)', () => {
    const f = facts({ against: 0, for: 0, split: 0, silent: 413 }, nat, { meetings: 526, lean_meetings: 526 })
    const c = pickCaption('water-fluoridation', f, nat)
    expect(c.kind).not.toBe('position')
    expect(c.basis).toMatch(/413 of 526 meetings have a reading so far; in all of them the public didn't speak on water fluoridation\. 113 meetings more have a reading in labels this page can't show yet\.$/)
  })

  it('no reading at all: says so under the count title', () => {
    const c = pickCaption('guns', facts({ against: 0, for: 0, split: 0, silent: 0 }, oh), oh)
    expect(c.basis).toMatch(/No meeting in Ohio has a reading of the public's position yet\./)
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
      'America hates data centers.',
    )
    expect(c.widerPlace).toBe('America')
    expect(c.basis).toMatch(/^Tuscaloosa, Alabama talked about data centers in 2 meetings\. Of its 2 meetings read, the public spoke in 1, under the 3 a conclusion of its own needs\. Across America, the public was against data centers in 300 of 340 meetings where it spoke\. /)
  })

  const NATIONAL_DC = { level: 'national' as const, state_code: null, state: null, lean_meetings: 900, public_against_meetings: 300, public_against_states: 30, public_for_meetings: 20, public_split_meetings: 20, public_silent_meetings: 560, disagreement_meetings: 0 }

  it('titles are the short conclusion only (#1222, owner 2026-11-26): no counts, no "AI reading", nothing appended', () => {
    const n = pickCaption('data-centers', facts({ against: 283, for: 30, split: 28, silent: 1487 }), nat)
    expect(captionText(n, 'data centers')).toBe('America hates data centers.')
    expect(n.basis).toMatch(/^The public was against data centers in 283 of 341 meetings where it spoke\. /)
    // A place too thin of its own: the nearest broader conclusion, as that simple sentence; the place's facts in the basis.
    const t = pickCaption('data-centers', facts({ against: 0, for: 1, split: 0, silent: 1 }, tus, { meetings: 2, wider: [NATIONAL_DC] }), tus)
    expect(captionText(t, 'data centers')).toBe('America hates data centers.')
    expect(t.basis).toMatch(/^Tuscaloosa, Alabama talked about data centers in 2 meetings\./)
    const sp = pickCaption('short-term-rentals', facts({ against: 30, for: 30, split: 10, silent: 0 }), nat)
    expect(captionText(sp, 'short-term rentals')).toBe('America is split on short-term rentals.')
    const ca: StoryScope = { stateCode: 'CA', stateName: 'California', city: null }
    expect(text('short-term-rentals', facts({ against: 30, for: 5, split: 2, silent: 0 }, ca), ca, 'short-term rentals')).toBe('California mostly wants limits on short-term rentals.')
    for (const c of [n, t, sp]) {
      const title = captionText(c, 'data centers')
      expect(title.length).toBeLessThanOrEqual(60)
      expect(title).not.toMatch(/AI|\d|;|In the United States/)
      expect(c.basis ?? '').not.toMatch(/AI read/)
    }
  })

  it("a place's own counted-speaker title still beats the broader scope's conclusion (p2 sits where a2 did)", () => {
    const f = facts({ against: 1, for: 0, split: 0, silent: 4 }, oh, { speakers: { for: 2, against: 12, question: 0, neutral: 0, states: 1 }, wider: [NATIONAL_DC] })
    const c = pickCaption('data-centers', f, oh)
    expect(c.kind).toBe('sentiment')
    expect(captionText(c, 'data centers')).toBe('Ohio hates data centers.')
  })

  it('p2 never states a zero for a place where the public did not speak', () => {
    const f = facts({ against: 0, for: 0, split: 0, silent: 5 }, oh, { wider: [NATIONAL_DC] })
    const c = pickCaption('data-centers', f, oh)
    expect(c.kind).toBe('wider_position')
    expect(c.basis).toMatch(/^Ohio talked about data centers in 700 meetings\. Of its 5 meetings read, the public spoke on it in none\./)
    expect(c.basis).not.toMatch(/\b0 /)
  })

  it('readings in off-list labels are not called "not read yet" in a conclusion basis (#1204)', () => {
    const f = facts({ against: 40, for: 5, split: 5, silent: 100 }, nat, { meetings: 300, lean_meetings: 170 })
    const c = pickCaption('pickleball', f, nat)
    expect(c.basis).toMatch(/20 meetings more have a reading in labels this page can't show yet\. 130 meetings not read yet\./)
  })

  it('a failed reading (null) adds no "no reading yet" claim', () => {
    const f = facts(null, oh)
    expect(pickCaption('guns', f, oh).basis).not.toMatch(/AI reading/)
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

const al: StoryScope = { stateCode: 'AL', stateName: 'Alabama', city: null }

describe('pickCaption (p) lower tier: the place named from 5 meetings where the public spoke (#1224, owner 2026-11-27)', () => {
  it('a majority below the hates floor names the place with "mostly opposes", never "hates"', () => {
    // 8 meetings where the public spoke (6 against, 2 split): under the state floor of 10 for "hates".
    const c = pickCaption('data-centers', facts({ against: 6, for: 0, split: 2, silent: 63 }, al, { meetings: 71 }), al)
    expect(c.kind).toBe('position')
    expect(c.place).toBe('Alabama')
    expect(captionText(c, 'data centers')).toBe('Alabama mostly opposes data centers.')
    expect(c.basis).toMatch(/^Most meetings were against data centers: 6 of 8 where the public spoke\. /)
  })

  it('a majority for, in the topic words', () => {
    const c = pickCaption('guns', facts({ against: 1, for: 5, split: 1, silent: 40 }, oh), oh)
    expect(captionText(c, 'gun control')).toBe('Ohio mostly favors gun limits.')
  })

  it('no majority from 5 meetings is split', () => {
    const c = pickCaption('guns', facts({ against: 2, for: 2, split: 2, silent: 40 }, oh), oh)
    expect(captionText(c, 'gun control')).toBe('Ohio is split on gun control.')
  })

  it('under 5 meetings where the public spoke keeps the broader fallback (the place is not the title)', () => {
    const c = pickCaption('data-centers', facts({ against: 3, for: 0, split: 1, silent: 60 }, al, { meetings: 64 }), al)
    expect(captionText(c, 'data centers')).not.toMatch(/^Alabama mostly/)
  })

  it('at or over the floor, "hates" still leads for its topics', () => {
    const c = pickCaption('data-centers', facts({ against: 12, for: 1, split: 1, silent: 40 }, al), al)
    expect(captionText(c, 'data centers')).toBe('Alabama hates data centers.')
  })
})

describe('withTopicBlank (#1224)', () => {
  it('turns the topic phrase in the words into the topic control', () => {
    expect(withTopicBlank([{ blank: 'place' }, ' mostly opposes data centers.'], 'data centers')).toEqual([
      { blank: 'place' },
      ' mostly opposes ',
      { blank: 'topic' },
      '.',
    ])
  })
  it('names the topic in brackets when the words do not', () => {
    expect(withTopicBlank([{ blank: 'place' }, ' mostly favors gun limits.'], 'gun control')).toEqual([
      { blank: 'place' },
      ' mostly favors gun limits',
      ' (',
      { blank: 'topic' },
      ').',
    ])
  })
  it('leaves a title that already has the control alone', () => {
    const t = [{ blank: 'place' as const }, ' hates ', { blank: 'topic' as const }, '.']
    expect(withTopicBlank(t, 'data centers')).toBe(t)
  })
})
