import { describe, expect, it } from 'vitest'
import type { TopicCaptionFacts } from '../api/topics'
import type { StoryScope } from './dataStory'
import { captionSubhead, captionText, pickCaption, type Caption } from './storyCaption'
import { STANCE_MIN_DECISIONS, STANCE_MIN_SPEAKERS, evidenceFacts, recordedEvidence, stanceSide, voteSide } from './stanceEvidence'

// Test stand-ins shaped like the caption-facts response (#1289). The Alabama fixture mirrors what the live API returned
// for /stories/data-centers?state=AL on 2026-11-27, the page the owner reported.
const al: StoryScope = { stateCode: 'AL', stateName: 'Alabama', city: null }
const nat: StoryScope = { stateName: null, city: null }

type Over = Partial<TopicCaptionFacts>
function facts(scope: StoryScope, over: Over = {}): TopicCaptionFacts {
  return {
    topic: 'data-centers',
    topic_id: 100001,
    scope: { level: scope.stateCode ? 'state' : 'national', state_code: scope.stateCode ?? null, state: scope.stateName, city: null },
    meetings: 71,
    states: [],
    top_state: null,
    ratio_to_next: null,
    place: null,
    places: null,
    speakers: { for: 0, against: 0, question: 0, neutral: 0, states: 0, meetings_reviewed: 24 },
    votes: { decisions: 1, for: 8, against: 1 },
    lean_meetings: 71,
    public_against_meetings: 6,
    public_for_meetings: 0,
    public_split_meetings: 2,
    public_silent_meetings: 63,
    disagreement_meetings: 0,
    disagreement_states: 0,
    wider: [
      {
        level: 'national', state_code: null, state: null, lean_meetings: 1828, public_against_meetings: 283, public_against_states: 32,
        public_for_meetings: 14, public_split_meetings: 44, public_silent_meetings: 1487, disagreement_meetings: 23,
      },
    ],
    ...over,
  }
}
const national = (over: Over = {}) =>
  facts(nat, {
    meetings: 1859,
    speakers: { for: 3, against: 18, question: 1, neutral: 7, states: 4, meetings_reviewed: 188 },
    votes: { decisions: 12, for: 79, against: 10 },
    lean_meetings: 1828,
    public_against_meetings: 283,
    public_against_states: 32,
    public_for_meetings: 14,
    public_split_meetings: 44,
    public_silent_meetings: 1487,
    disagreement_meetings: 23,
    wider: null,
    ...over,
  })
const title = (c: Caption) => captionText(c, 'data centers')

/** The check the owner asked for: a stance headline never takes the side opposite the recorded votes. */
function expectAgreesWithVotes(c: Caption, f: TopicCaptionFacts) {
  const v = voteSide(recordedEvidence(f))
  const s = stanceSide(c)
  if (v && s) expect(s, `"${title(c)}" against votes ${JSON.stringify(f.votes)}`).toBe(v)
}

describe('stance headline: below the minimum (#1289)', () => {
  it('Alabama (1 decision passed 8–1, no speakers in 24 meetings) says there is not enough to say, with the facts', () => {
    const f = facts(al)
    const c = pickCaption('data-centers', f, al)
    expect(c.kind).toBe('insufficient')
    expect(title(c)).not.toMatch(/oppos|hates|support/)
    expect(captionText(c, 'data centers')).toBe('Not enough recorded activity to say.')
    expect(c.basis).toMatch(/^One decision passed 8–1; no public speakers in 24 meetings reviewed\./)
    expect(c.basis).not.toMatch(/%/)
    expect(captionSubhead(c, 'data-centers', al)).not.toMatch(/mostly|hates/)
  })

  it('the minimum is fewer than 3 decisions and fewer than 5 speakers', () => {
    expect(STANCE_MIN_DECISIONS).toBe(3)
    expect(STANCE_MIN_SPEAKERS).toBe(5)
    const sp = (n: number) => ({ for: 0, against: n, question: 0, neutral: 0, states: 1, meetings_reviewed: 24 })
    // Both under: not enough.
    expect(pickCaption('data-centers', facts(al, { votes: { decisions: 2, for: 3, against: 7 }, speakers: sp(4) }), al).kind).toBe('insufficient')
    // 3 decisions: enough (the votes here are against, so the against reading stands).
    expect(pickCaption('data-centers', facts(al, { votes: { decisions: 3, for: 4, against: 11 }, speakers: sp(0) }), al).kind).toBe('position')
    // 5 speakers: enough.
    expect(pickCaption('data-centers', facts(al, { votes: { decisions: 0, for: 0, against: 0 }, speakers: sp(5) }), al).kind).toBe('position')
  })

  it('states the facts plainly for zero, one and several decisions', () => {
    expect(evidenceFacts(recordedEvidence(facts(al, { votes: { decisions: 0, for: 0, against: 0 } })))).toBe(
      'No decision with a recorded vote; no public speakers in 24 meetings reviewed.',
    )
    expect(evidenceFacts(recordedEvidence(facts(al, { votes: { decisions: 2, for: 9, against: 5 }, speakers: { for: 1, against: 2, question: 0, neutral: 0, states: 1, meetings_reviewed: 24 } })))).toBe(
      '2 decisions with recorded votes, 9 for and 5 against in all; 3 public speakers in 24 meetings reviewed.',
    )
    expect(evidenceFacts(recordedEvidence(facts(al, { votes: { decisions: 1, for: 2, against: 5 } })))).toMatch(/^One decision failed 2–5;/)
  })

  it('a data-center scope with no meeting reviewed (speakers and votes null) is below the minimum too', () => {
    const c = pickCaption('data-centers', facts(al, { speakers: null, votes: null }), al)
    expect(c.kind).toBe('insufficient')
    expect(c.basis).toMatch(/^Recorded votes are not available yet; public speakers are not available yet\./)
  })

  it('a topic with no hand counts or votes on record is not held to the minimum (nothing to count yet)', () => {
    const f = facts(al, { topic: 'guns', speakers: null, votes: null, public_against_meetings: 10, public_for_meetings: 41, public_split_meetings: 12, lean_meetings: 63, public_silent_meetings: 0 })
    const c = pickCaption('guns', f, al)
    expect(c.kind).toBe('position')
  })
})

describe('stance headline agrees with the recorded votes (#1289)', () => {
  it('the national "hates" reading becomes "divided" while recorded votes went 79–10 for', () => {
    const f = national()
    const c = pickCaption('data-centers', f, nat)
    expect(title(c)).toBe('America is divided on data centers.')
    expect(c.basis).toMatch(/Recorded votes: 79 for and 10 against, in 12 decisions\./)
    expectAgreesWithVotes(c, f)
  })

  it('an against reading with votes against stands', () => {
    const f = national({ votes: { decisions: 12, for: 10, against: 79 } })
    const c = pickCaption('data-centers', f, nat)
    expect(title(c)).toBe('America hates data centers.')
    expectAgreesWithVotes(c, f)
  })

  it('a "for" reading with votes against becomes "divided"', () => {
    const f = facts(al, {
      votes: { decisions: 4, for: 3, against: 20 },
      public_against_meetings: 1, public_for_meetings: 7, public_split_meetings: 0, public_silent_meetings: 63,
    })
    const c = pickCaption('data-centers', f, al)
    expect(title(c)).toBe('Alabama is divided on data centers.')
    expectAgreesWithVotes(c, f)
  })

  it('no fixture yields a headline on the side opposite its votes', () => {
    const cases: Array<[TopicCaptionFacts, StoryScope]> = []
    for (const votes of [
      { decisions: 0, for: 0, against: 0 }, { decisions: 1, for: 8, against: 1 }, { decisions: 3, for: 20, against: 2 },
      { decisions: 5, for: 2, against: 30 }, { decisions: 12, for: 79, against: 10 },
    ]) {
      for (const n of [0, 4, 12]) {
        const speakers = { for: 0, against: n, question: 0, neutral: 0, states: 1, meetings_reviewed: 24 }
        cases.push([facts(al, { votes, speakers }), al])
        cases.push([facts(al, { votes, speakers, public_against_meetings: 0, public_for_meetings: 8 }), al])
        cases.push([national({ votes, speakers }), nat])
      }
    }
    for (const [f, s] of cases) expectAgreesWithVotes(pickCaption('data-centers', f, s), f)
  })
})
