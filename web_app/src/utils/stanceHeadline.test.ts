import { describe, expect, it } from 'vitest'
import type { TopicCaptionFacts } from '../api/topics'
import type { StoryScope } from './dataStory'
import { captionSubhead, captionText, pickCaption, type Caption } from './storyCaption'
import { STANCE_MIN_DECISIONS, STANCE_MIN_POSITION_MEETINGS, STANCE_MIN_SPEAKERS, disagreementLine, disagreementParts, evidenceFacts, namedSides, namedSidesClause, officialPositionsLine, publicPositionsLine, recordedEvidence, stanceSide, voteSide } from './stanceEvidence'

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
    // #1313: the topic is an inline control in the sentence, never "( ▾ )" appended in brackets.
    expect(captionText(c, 'data centers')).toBe('Not enough recorded activity on data centers to say.')
    expect(c.template).toContainEqual({ blank: 'topic' })
    expect(c.basis).toMatch(/^One decision passed 8–1; no public speakers in 24 meetings reviewed by hand\./)
    // #1313: the reading of the transcripts names its own source and scope, so it can't read as contradicting the hand count.
    expect(c.basis).toContain('A reading of all 71 meeting transcripts found the public speaking on data centers in 8 (6 against and both sides spoke at 2).')
    expect(c.basis).not.toMatch(/the public spoke in 8/)
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
      'No decision with a recorded vote; no public speakers in 24 meetings reviewed by hand.',
    )
    expect(evidenceFacts(recordedEvidence(facts(al, { votes: { decisions: 2, for: 9, against: 5 }, speakers: { for: 1, against: 2, question: 0, neutral: 0, states: 1, meetings_reviewed: 24 } })))).toBe(
      '2 decisions with recorded votes, 9 yes and 5 no votes in all; 3 public speakers in 24 meetings reviewed by hand.',
    )
    expect(evidenceFacts(recordedEvidence(facts(al, { votes: { decisions: 1, for: 2, against: 5 } })))).toMatch(/^One decision failed 2–5;/)
  })

  it('a data-center scope with no meeting reviewed (speakers and votes null) is below the minimum too', () => {
    const c = pickCaption('data-centers', facts(al, { speakers: null, votes: null }), al)
    expect(c.kind).toBe('insufficient')
    expect(c.basis).toMatch(/^Recorded votes are not available yet; public speakers are not available yet\./)
  })

  it('a reading where the public never spoke, and meetings not read yet, are said plainly (#1313)', () => {
    const c = pickCaption('data-centers', facts(al, { meetings: 10, public_against_meetings: 0, public_split_meetings: 0, public_for_meetings: 0, public_silent_meetings: 9, lean_meetings: 9 }), al)
    // No stance from the reading here, so the title is not a stance: the check only replaces stance titles.
    expect(c.kind).not.toBe('position')
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

describe('#1290: votes read by which way they went, and the speaker sources reconciled', () => {
  // Live shapes, 27 Nov 2026: Alabama's one vote ("Zoning Ordinance Delayed", 8–1) went for data centers; nationally 7 of the
  // 12 tallied decisions went for and 5 against (moratoriums and a denial), so the votes are mixed.
  const alLive = (over: Over = {}) =>
    facts(al, { votes: { decisions: 1, for: 8, against: 1, decisions_for: 1, decisions_against: 0 }, caption_comments: { comments: 62, governments: 10 }, ...over })

  it('Alabama: comments in our captions mean people spoke, so never "no public speakers"; the reading is labelled', () => {
    const c = pickCaption('data-centers', alLive(), al)
    expect(c.kind).toBe('insufficient')
    expect(c.basis).toMatch(
      /^One decision passed 8–1; no speaker’s side is recorded in 24 meetings reviewed by hand, and the 62 public comments in our captions are not sorted by side yet\. /,
    )
    expect(c.basis).not.toMatch(/no public speakers/)
    // The transcript reading names its own source (#1313), so it never reads as counted speakers.
    expect(c.basis).toContain('A reading of all 71 meeting transcripts found the public speaking on data centers in 8')
  })
  it('with no caption comments, reviewed meetings with nobody counted are "no public speakers"', () => {
    expect(evidenceFacts(recordedEvidence(alLive({ caption_comments: { comments: 0, governments: 0 } })))).toBe(
      'One decision passed 8–1; no public speakers in 24 meetings reviewed by hand.',
    )
  })
  it('a yes on a moratorium is not support: votes lean by decision side, two thirds or neither', () => {
    // 11 of 12 motions passed (79–10), but 5 of them paused or denied data centers: mixed, so no lean.
    const mixed = national({ votes: { decisions: 12, for: 79, against: 10, decisions_for: 7, decisions_against: 5 } })
    expect(voteSide(recordedEvidence(mixed))).toBeNull()
    expect(title(pickCaption('data-centers', mixed, nat))).toBe('America hates data centers.')
    const allFor = national({ votes: { decisions: 3, for: 20, against: 2, decisions_for: 3, decisions_against: 0 } })
    expect(voteSide(recordedEvidence(allFor))).toBe('for')
    const allAgainst = national({ votes: { decisions: 3, for: 27, against: 0, decisions_for: 0, decisions_against: 3 } })
    expect(voteSide(recordedEvidence(allAgainst))).toBe('against')
  })
  it('fails when a stance headline disagrees with the votes read by side', () => {
    const allFor = national({ votes: { decisions: 3, for: 20, against: 2, decisions_for: 3, decisions_against: 0 } })
    const c = pickCaption('data-centers', allFor, nat)
    expectAgreesWithVotes(c, allFor)
    expect(title(c)).toBe('America is divided on data centers.')
    expect(c.basis).toMatch(/ Recorded votes went the other way: 3 of 3 decisions with a recorded vote went for data centers\.$/)
    // Votes that went against data centers back an against headline.
    const allAgainst = national({ votes: { decisions: 3, for: 27, against: 0, decisions_for: 0, decisions_against: 3 } })
    expect(title(pickCaption('data-centers', allAgainst, nat))).toBe('America hates data centers.')
  })
})

describe('#1330: every recorded position counts, public and official, and disagreement is said', () => {
  // Live shapes, 27 Nov 2026 (caption facts for data centers): Alabama 32 meetings with a position (public 6 against and 2
  // split; officials 7 against, 8 for, 13 divided), 4 with both, one vote 8–1 that went for data centers.
  const alAll = (over: Over = {}) =>
    facts(al, {
      votes: { decisions: 1, for: 8, against: 1, decisions_for: 1, decisions_against: 0 },
      caption_comments: { comments: 62, governments: 10 },
      official_against_meetings: 7,
      official_for_meetings: 8,
      official_divided_meetings: 13,
      position_meetings: 32,
      both_position_meetings: 4,
      ...over,
    })

  it('the minimum is fewer than 5 meetings with any position, public or official (and fewer than 3 voted decisions)', () => {
    expect(STANCE_MIN_POSITION_MEETINGS).toBe(5)
    const at = (n: number) => pickCaption('data-centers', alAll({ position_meetings: n }), al).kind
    expect(at(STANCE_MIN_POSITION_MEETINGS - 1)).toBe('insufficient')
    expect(at(STANCE_MIN_POSITION_MEETINGS)).not.toBe('insufficient')
  })
  it('Alabama clears the minimum on 32 meetings with a position, and its title agrees with the 8–1 vote: divided', () => {
    const c = pickCaption('data-centers', alAll(), al)
    expect(title(c)).toBe('Alabama is divided on data centers.')
    expectAgreesWithVotes(c, alAll())
    expect(c.basis).toMatch(/Recorded votes went the other way: 1 of 1 decision with a recorded vote went for data centers\.$/)
  })
  it('says where officials sided against the public, with its denominator, and nothing when they never did', () => {
    const ga = recordedEvidence(facts({ stateCode: 'GA', stateName: 'Georgia', city: null }, { disagreement_meetings: 11, both_position_meetings: 27 }))
    expect(disagreementLine(ga, 'In Georgia')).toBe('In Georgia, officials sided against the public in 11 of 27 meetings where both took a side.')
    expect(disagreementLine(recordedEvidence(alAll()), 'In Alabama')).toBeNull()
  })
  it('the positions lines name who: the public and officials, no zero side', () => {
    const e = recordedEvidence(alAll())
    expect(publicPositionsLine(e)).toBe('Public: 6 against · 2 both sides spoke (8 meetings)')
    expect(officialPositionsLine(e)).toBe('Officials: 7 against · 8 for · 13 divided (28 meetings); recorded votes: 1 decision for, 0 against')
  })
  it('below the minimum, the facts count the meetings with a position too', () => {
    const c = pickCaption('data-centers', alAll({ position_meetings: 3 }), al)
    expect(c.basis).toMatch(/the public or officials took a position in 3 meetings read\./)
  })
})

describe('#1330: named supporters and opposers come from #1327 supported_by / opposed_by', () => {
  it('counts distinct names, and says nothing without the fields', () => {
    const items = [
      { supported_by: [{ name: 'John Faile' }, { name: 'Ann B.' }], opposed_by: [{ name: 'Sam C.' }] },
      { supported_by: [{ name: 'John Faile' }], opposed_by: [] },
    ]
    expect(namedSides(items)).toEqual({ supporters: 2, opposers: 1 })
    expect(namedSidesClause(namedSides(items))).toBe('named supporters 2 · opposers 1')
    expect(namedSides([{}, {}])).toBeNull()
    expect(namedSidesClause({ supporters: 0, opposers: 0 })).toBeNull()
  })
})

describe('#1330: the disagreement count is its own part, and singular reads right', () => {
  it('splits into before / count / after, and "1 of 1 meeting"', () => {
    const e = recordedEvidence(facts({ stateCode: 'AL', stateName: 'Alabama', city: 'District 1' }, { disagreement_meetings: 1, both_position_meetings: 1 }))
    expect(disagreementParts(e, 'In District 1, Alabama')).toEqual({
      before: 'In District 1, Alabama, officials sided against the public in ',
      count: '1',
      after: ' of 1 meeting where both took a side.',
    })
  })
})
