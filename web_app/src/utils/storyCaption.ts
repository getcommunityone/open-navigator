// The caption picker (#1125): the one title a topic's record supports for one scope (national, state or city), shared by
// the story header on /stories/<topic>, the home story card and the home Browse Topics tiles.
//
// Rules, in order; each needs its own real counts and otherwise falls through to the next (CLAUDE.md, No Fabricated Data).
// Thresholds and the reasons for them: web_docs/docs/development/story-captions.md.
//   a. sentiment ("[Place] hates [topic]."): confident public-against meetings at volume (AI reading), or the story's
//      counted-speaker gate. The AI's "for" and "mixed" labels are unreliable and never used, in a count or a ratio.
//   b. disagreement ("[Place] is divided on [topic]."): officials sided against the public (AI reading) at volume, or
//      counted speakers split for and against.
//   c. state_gap: the place leads the other states (or places in its state) by meetings; a near tie names both.
//   d. volume: the place's meeting count.
//   e. question: the topic's question.
// No caption or basis line ever states a zero ("0 spoke for"): a zero clause is left out (owner rule).
import type { TopicCaptionFacts } from '../api/topics'
import { STORIES, storyScopeLabel, type StoryScope, type StoryTitlePart } from './dataStory'

// --- thresholds (story-captions.md says why) -----------------------------------------------------------------------

/** (a) Confident public-against meetings (AI reading) before "[Place] hates [topic]." leads, by scope level. */
export const HATES_MIN_MEETINGS = { national: 50, state: 10, city: 3 } as const
/** (b) Meetings where officials sided against the public (AI reading) before "[Place] is divided on [topic]." leads. */
export const DISAGREEMENT_MIN_MEETINGS = 10
/** (b) Counted speakers on each side before a for/against split reads as divided. */
export const SPLIT_MIN_SPEAKERS_PER_SIDE = 10
/** (b) The smaller side's share of for + against before it counts as a split (not a lopsided stance). */
export const SPLIT_MIN_MINORITY_SHARE = 0.35
/** (c) The top state's meetings over the next state's before it is named alone; below this the two are named together. */
export const STATE_GAP_MIN_RATIO = 1.25
/** (c) Meetings the leading state (or a ranked state) needs. */
export const STATE_GAP_MIN_MEETINGS = 50
/** (c) State scope: a state ranked this high or better is named by its rank. */
export const STATE_RANK_MAX = 3
/** (c) City scope: meetings the place needs before it is ranked among its state's places. */
export const PLACE_GAP_MIN_MEETINGS = 10

// --- per-topic copy ------------------------------------------------------------------------------------------------

export interface CaptionCopy {
  /** The topic blank: "short-term rentals". */
  topic: string
  /** The caption-facts slug, or null for a guide with no meeting record behind it (it always shows its question). */
  facts: string | null
  /** The volume verb: "[California] took up [short-term rentals] in 570 meetings." */
  verb: string
  /**
   * The (a) verb ("hates"), or absent when "against" has no clear direction for the topic (guns, short-term rentals,
   * fluoridation: the public can be against the thing or against limits on it), so (a) is skipped.
   */
  hates?: string
  /** (b) basis wording after "officials", when officials sided against the public, around the topic. */
  officials: { before: string; after: string }
  /** The question (e), with the place and topic blanks. */
  question: StoryTitlePart[]
}

const P = { blank: 'place' } as const
const T = { blank: 'topic' } as const
const askMeetings: StoryTitlePart[] = ['What did local meetings in ', P, ' say about ', T, '?']
const sidedAgainst = { before: 'sided against the public on ', after: '' }

export const CAPTION_COPY: Record<string, CaptionCopy> = {
  'data-centers': {
    topic: 'data centers',
    facts: 'data-centers',
    verb: 'talked about',
    hates: 'hates',
    officials: { before: 'backed ', after: ' while the public pushed back' },
    question: askMeetings,
  },
  'short-term-rentals': {
    topic: 'short-term rentals',
    facts: 'short-term-rentals',
    verb: 'took up',
    officials: sidedAgainst,
    question: ['Who gets to rent out a home in ', P, '? What meetings said about ', T, '.'],
  },
  flock: {
    topic: 'Flock and license plate readers',
    facts: 'flock',
    verb: 'weighed',
    hates: 'hates',
    officials: sidedAgainst,
    question: ['Who is watching the roads in ', P, '? What meetings said about ', T, '.'],
  },
  'license-plate-readers': {
    topic: 'Flock and license plate readers',
    facts: 'license-plate-readers',
    verb: 'weighed',
    hates: 'hates',
    officials: sidedAgainst,
    question: askMeetings,
  },
  guns: {
    topic: 'guns',
    facts: 'guns',
    verb: 'took up',
    officials: sidedAgainst,
    question: askMeetings,
  },
  pickleball: {
    topic: 'pickleball',
    facts: 'pickleball',
    verb: 'brought up',
    hates: 'hates',
    officials: sidedAgainst,
    question: ['Where do the courts go in ', P, '? What meetings said about ', T, '.'],
  },
  'bike-lanes': {
    topic: 'bicycle transportation',
    facts: 'bike-lanes',
    verb: 'took up',
    officials: sidedAgainst,
    question: askMeetings,
  },
  'water-fluoridation': {
    topic: 'water fluoridation',
    facts: 'water-fluoridation',
    verb: 'took up',
    officials: sidedAgainst,
    question: askMeetings,
  },
  // Guides (#1078, #1079): no meeting record backs them yet, so they always ask their question.
  'starting-a-nonprofit': {
    topic: 'a nonprofit',
    facts: null,
    verb: 'talked about',
    officials: sidedAgainst,
    question: ['What does it take to start ', T, ' in ', P, '?'],
  },
  insurance: {
    topic: 'insurance',
    facts: null,
    verb: 'talked about',
    officials: sidedAgainst,
    question: ['Are you paying too much for ', T, ' in ', P, '?'],
  },
}

// --- the picker ----------------------------------------------------------------------------------------------------

export type CaptionKind = 'disagreement' | 'sentiment' | 'state_gap' | 'volume' | 'question'

export interface Caption {
  kind: CaptionKind
  template: StoryTitlePart[]
  /** How the place blank reads: "America", "Georgia", "Tuscaloosa, Alabama" (or the leading state(s), for a national state_gap). */
  place: string
  /** The line of real numbers under the caption; null for the question. Never states a zero. */
  basis: string | null
  /** True when the caption rests on an AI reading of transcripts (Jev), not counted speakers: the UI labels it. */
  ai: boolean
}

const fmt = (n: number) => n.toLocaleString('en-US')
const meetingsWord = (n: number) => `${fmt(n)} ${n === 1 ? 'meeting' : 'meetings'}`
const ORDINALS = ['', '', '2nd', '3rd', '4th', '5th']
/** "twice" / "three times" for a whole-number multiple of at least 2, else null. */
function timesWord(ratio: number): string | null {
  const n = Math.floor(ratio)
  if (n < 2) return null
  return n === 2 ? 'twice' : n === 3 ? 'three times' : n === 4 ? 'four times' : `${n} times`
}
/** "a, b and c", dropping empty parts. */
function joinAnd(parts: string[]): string {
  const p = parts.filter(Boolean)
  return p.length <= 1 ? (p[0] ?? '') : `${p.slice(0, -1).join(', ')} and ${p[p.length - 1]}`
}

/** The facts answer the scope asked for (never a stale scope's numbers under the new label). */
function factsMatchScope(facts: TopicCaptionFacts, scope: StoryScope): boolean {
  const want = scope.stateCode ?? null
  if ((facts.scope.state_code ?? null) !== want) return false
  const wantCity = want ? (scope.city ?? '').toLowerCase() : ''
  return (facts.scope.city ?? '').toLowerCase() === wantCity
}

type Speakers = NonNullable<TopicCaptionFacts['speakers']>

/** "Of 12 speakers on record at local meetings in Arizona, 11 spoke against." Zero clauses left out. */
function speakerBasis(sp: Speakers, where: string): string {
  const total = sp.for + sp.against + sp.question + sp.neutral
  const parts = [
    sp.against > 0 ? `${fmt(sp.against)} spoke against` : '',
    sp.for > 0 ? `${fmt(sp.for)} spoke for` : '',
    sp.question > 0 ? `${fmt(sp.question)} asked a question` : '',
    sp.neutral > 0 ? `${fmt(sp.neutral)} took no side` : '',
  ]
  return `Of ${fmt(total)} ${total === 1 ? 'speaker' : 'speakers'} on record at local meetings ${where}, ${joinAnd(parts)}.`
}

/**
 * The one title the record supports for `topicKey` (a `CAPTION_COPY` key) in `scope`. `facts` is the caption-facts response
 * for exactly that scope (null while loading or when it failed): with no facts the topic asks its question. Every number in
 * the result comes from `facts`.
 */
export function pickCaption(topicKey: string, facts: TopicCaptionFacts | null | undefined, scope: StoryScope): Caption {
  const copy: CaptionCopy = CAPTION_COPY[topicKey] ?? {
    topic: topicKey.replace(/-/g, ' '),
    facts: topicKey,
    verb: 'talked about',
    officials: sidedAgainst,
    question: askMeetings,
  }
  const national = !scope.stateName
  const level: keyof typeof HATES_MIN_MEETINGS = national ? 'national' : scope.city ? 'city' : 'state'
  const label = storyScopeLabel(scope)
  const place = national ? 'America' : label
  const where = national ? 'nationwide' : `in ${label}`
  const question: Caption = {
    kind: 'question',
    template: copy.question,
    place: national ? 'the United States' : label,
    basis: null,
    ai: false,
  }
  if (!copy.facts || !facts || !factsMatchScope(facts, scope)) return question
  const sp = facts.speakers
  const dis = facts.disagreement_meetings ?? 0

  // (a) "[Place] hates [topic]."
  if (copy.hates) {
    const against = facts.public_against_meetings ?? 0
    const story = STORIES[topicKey]
    const gate = story?.conclusion
    const total = sp ? sp.for + sp.against + sp.question + sp.neutral : 0
    const speakersPass = Boolean(
      gate && sp && gate.side === 'against' && total >= gate.minSpeakers && sp.against > 0 && sp.against >= gate.minRatio * sp.for,
    )
    const leanPasses = against >= HATES_MIN_MEETINGS[level]
    if (leanPasses || speakersPass) {
      const lean = leanPasses
        ? `In ${meetingsWord(against)} ${where}, Jev (an AI classifier) read the public as mostly against ${copy.topic} (AI reading).`
        : ''
      const counted = speakersPass && sp ? speakerBasis(sp, where) : ''
      return {
        kind: 'sentiment',
        template: [P, ` ${copy.hates} `, T, '.'],
        place,
        basis: [lean, counted].filter(Boolean).join(' '),
        ai: leanPasses,
      }
    }
  }

  // (b) "[Place] is divided on [topic]."
  if (dis >= DISAGREEMENT_MIN_MEETINGS) {
    const states = facts.disagreement_states ?? 0
    const span = national ? (states > 1 ? ` across ${fmt(states)} states` : '') : ` ${where}`
    return {
      kind: 'disagreement',
      template: [P, ' is divided on ', T, '.'],
      place,
      basis: `In ${meetingsWord(dis)}${span}, officials ${copy.officials.before}${copy.topic}${copy.officials.after} (AI reading).`,
      ai: true,
    }
  }
  if (sp) {
    const lo = Math.min(sp.for, sp.against)
    const hi = Math.max(sp.for, sp.against)
    if (lo >= SPLIT_MIN_SPEAKERS_PER_SIDE && lo / (lo + hi) >= SPLIT_MIN_MINORITY_SHARE) {
      return { kind: 'disagreement', template: [P, ' is divided on ', T, '.'], place, basis: speakerBasis(sp, where), ai: false }
    }
  }

  // (c) Volume with state differences.
  const gap = stateGap(copy, facts, scope)
  if (gap) return gap

  // (d) Plain volume.
  const m = facts.meetings ?? 0
  if (m > 0) {
    return {
      kind: 'volume',
      template: [P, ` ${copy.verb} `, T, ` in ${meetingsWord(m)}.`],
      place,
      basis: `Counted from local meeting recordings and transcripts ${where} that mention the topic.`,
      ai: false,
    }
  }
  // (e) The question.
  return question
}

const COVERAGE = 'Counted from local meeting recordings and transcripts on record; how many meetings are on record varies by state.'

function stateGap(copy: CaptionCopy, facts: TopicCaptionFacts, scope: StoryScope): Caption | null {
  const states = facts.states.filter((s) => s.meetings > 0).sort((a, b) => b.meetings - a.meetings || a.state_code.localeCompare(b.state_code))
  const name = (s: { state: string | null; state_code: string }) => s.state ?? s.state_code
  const total = facts.meetings ?? 0
  const lead = (n: number, next: number) => {
    const times = timesWord(n / next)
    return times ? `more than ${times} any other state` : 'more than any other state'
  }

  // City scope: the place against the other places in its state.
  if (scope.city && scope.stateName) {
    const places = (facts.places ?? []).filter((p) => p.meetings > 0)
    const mine = facts.place ? places.find((p) => p.name === facts.place) : undefined
    const next = places.find((p) => p !== mine)
    if (!mine || mine.meetings < PLACE_GAP_MIN_MEETINGS || !next || mine.meetings <= next.meetings) return null
    return {
      kind: 'state_gap',
      template: [P, ` ${copy.verb} `, T, ` in ${meetingsWord(mine.meetings)}, more than any other place in ${scope.stateName}.`],
      place: storyScopeLabel(scope),
      basis: `Next: ${next.name}, ${meetingsWord(next.meetings)}. ${COVERAGE}`,
      ai: false,
    }
  }

  if (!scope.stateCode) {
    const [top, next] = states
    if (!top || !next || top.meetings < STATE_GAP_MIN_MEETINGS) return null
    if (top.meetings >= STATE_GAP_MIN_RATIO * next.meetings) {
      return {
        kind: 'state_gap',
        template: [P, ` ${copy.verb} `, T, ` in ${meetingsWord(top.meetings)}, ${lead(top.meetings, next.meetings)}.`],
        place: name(top),
        basis: `Next: ${name(next)}, ${meetingsWord(next.meetings)}. Of ${meetingsWord(total)} nationwide. ${COVERAGE}`,
        ai: false,
      }
    }
    // A near tie names both, and only when they lead the third state clearly enough to be a pair.
    const third = states[2]
    if (next.meetings >= STATE_GAP_MIN_MEETINGS && (!third || next.meetings > third.meetings)) {
      const counts = top.meetings === next.meetings ? `${meetingsWord(top.meetings)} each` : `${fmt(top.meetings)} and ${meetingsWord(next.meetings)}`
      return {
        kind: 'state_gap',
        template: [P, ` ${copy.verb} `, T, ` most: ${counts}.`],
        place: `${name(top)} and ${name(next)}`,
        basis: `${third ? `Next: ${name(third)}, ${meetingsWord(third.meetings)}. ` : ''}Of ${meetingsWord(total)} nationwide. ${COVERAGE}`,
        ai: false,
      }
    }
    return null
  }

  // State scope: the state's rank among the states.
  const idx = states.findIndex((s) => s.state_code === scope.stateCode)
  if (idx < 0) return null
  const mine = states[idx]!
  if (mine.meetings < STATE_GAP_MIN_MEETINGS) return null
  if (idx === 0) {
    const next = states[1]
    if (next && mine.meetings > next.meetings) {
      return {
        kind: 'state_gap',
        template: [P, ` ${copy.verb} `, T, ` in ${meetingsWord(mine.meetings)}, ${lead(mine.meetings, next.meetings)}.`],
        place: storyScopeLabel(scope),
        basis: `Next: ${name(next)}, ${meetingsWord(next.meetings)}. ${COVERAGE}`,
        ai: false,
      }
    }
  }
  // Ranked 2nd or 3rd, and strictly ahead of the state below (a tie has no rank to state).
  const below = states[idx + 1]
  if (idx > 0 && idx + 1 <= STATE_RANK_MAX && states[idx - 1]!.meetings > mine.meetings && (!below || mine.meetings > below.meetings)) {
    return {
      kind: 'state_gap',
      template: [P, ` ${copy.verb} `, T, ` in ${meetingsWord(mine.meetings)}, the ${ORDINALS[idx + 1]} most of any state.`],
      place: storyScopeLabel(scope),
      basis: `Ahead: ${states.slice(0, idx).map((s) => `${name(s)} (${fmt(s.meetings)})`).join(', ')}. ${COVERAGE}`,
      ai: false,
    }
  }
  return null
}

/** The caption as one plain sentence (for a tile, an aria-label or a test): the blanks filled in. */
export function captionText(caption: Caption, topic: string): string {
  return caption.template.map((p) => (typeof p === 'string' ? p : p.blank === 'place' ? caption.place : topic)).join('')
}
