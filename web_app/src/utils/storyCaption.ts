// The caption picker (#1125): the strongest true statement a topic's record supports for one scope (national, state or
// city), for the story title on /stories/<topic> and the topic tile on the home Browse Topics strip.
//
// Rules, in order; each one needs its own real counts and otherwise falls through to the next (CLAUDE.md, No Fabricated
// Data). The thresholds and the reasons for them: web_docs/docs/development/story-captions.md.
//   1. disagreement: officials sided against the public (AI reading) at volume, or speakers split for and against.
//   2. sentiment:    the story's existing speaker gate ("America hates data centers."), then the public's lean (AI reading).
//   3. state_gap:    the place leads the other states (or places in its state) by meetings, or per resident.
//   4. volume:       the place's meeting count.
//   5. question:     the topic's question.
// The place and the topic stay blanks in the template, as in `storyTitle`.
import type { TopicCaptionFacts } from '../api/topics'
import { STORIES, storyConclusion, storyScopeLabel, type StoryScope, type StoryTitlePart } from './dataStory'

// --- thresholds (story-captions.md says why) -----------------------------------------------------------------------

/** Rule 1: meetings where officials sided against the public (AI reading) before the split leads. */
export const DISAGREEMENT_MIN_MEETINGS = 10
/** Rule 1: speakers on each side before a for/against split leads. */
export const SPLIT_MIN_SPEAKERS_PER_SIDE = 10
/** Rule 1: the smaller side's share of for + against before it counts as a split (not a lopsided stance). */
export const SPLIT_MIN_MINORITY_SHARE = 0.35
/** Rule 2 (AI reading): meetings where the public leaned one way before that leads. */
export const PUBLIC_LEAN_MIN_MEETINGS = 20
/** Rule 2 (AI reading): those meetings' share of all meetings read in scope. */
export const PUBLIC_LEAN_MIN_SHARE = 0.25
/** Rule 3 (national): the top state's meetings over the next state's. */
export const STATE_GAP_MIN_RATIO = 1.5
/** Rule 3: meetings the leading state (or a ranked state) needs. */
export const STATE_GAP_MIN_MEETINGS = 50
/** Rule 3 (state scope): a state ranked this high or better is named by its rank. */
export const STATE_RANK_MAX = 3
/** Rule 3 (per resident): meetings a state needs before its rate per resident is compared. */
export const PER_CAPITA_MIN_MEETINGS = 100
/** Rule 3 (per resident): the leading rate over the next state's rate. */
export const PER_CAPITA_MIN_RATIO = 1.5
/** Rule 3 (city scope): meetings the place needs before it is ranked among its state's places. */
export const PLACE_GAP_MIN_MEETINGS = 10

// --- per-topic copy ------------------------------------------------------------------------------------------------

export interface CaptionCopy {
  /** The topic blank: "short-term rentals". */
  topic: string
  /** The caption-facts slug, or null for a guide with no meeting record behind it (it always shows its question). */
  facts: string | null
  /** The volume verb: "[California] took up [short-term rentals] in 570 meetings." */
  verb: string
  /** Rule 1 wording after "officials", when officials sided against the public; ends with the topic blank's tail. */
  officials: { before: string; after: string }
  /** The question (rule 5), with the place and topic blanks. */
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
    topic: 'Flock and plate-reader cameras',
    facts: 'flock',
    verb: 'weighed',
    officials: sidedAgainst,
    question: ['Who is watching the roads in ', P, '? What meetings said about ', T, '.'],
  },
  'license-plate-readers': {
    topic: 'license plate readers',
    facts: 'license-plate-readers',
    verb: 'weighed',
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
  /** How the place blank reads: "America", "Georgia", "Tuscaloosa, Alabama" (or the leading state, for a national state_gap). */
  place: string
  /** The line of real numbers under the caption; null for the question. */
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

/** The facts answer the scope asked for (never a stale scope's numbers under the new label). */
function factsMatchScope(facts: TopicCaptionFacts, scope: StoryScope): boolean {
  const want = scope.stateCode ?? null
  if ((facts.scope.state_code ?? null) !== want) return false
  const wantCity = want ? (scope.city ?? '').toLowerCase() : ''
  return (facts.scope.city ?? '').toLowerCase() === wantCity
}

/**
 * The strongest statement the record supports for `topicKey` (a `CAPTION_COPY` key) in `scope`. `facts` is the
 * caption-facts response for exactly that scope (null while loading or when it failed): with no facts the topic asks its
 * question. Every number in the result comes from `facts`.
 */
export function pickCaption(topicKey: string, facts: TopicCaptionFacts | null | undefined, scope: StoryScope): Caption {
  const copy = CAPTION_COPY[topicKey] ?? {
    topic: topicKey.replace(/-/g, ' '),
    facts: topicKey,
    verb: 'talked about',
    officials: sidedAgainst,
    question: askMeetings,
  }
  const national = !scope.stateName
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

  // 1. Disagreement at volume.
  const dis = facts.disagreement_meetings
  if (dis != null && dis >= DISAGREEMENT_MIN_MEETINGS) {
    const across = scope.city ? 'in' : 'across'
    const statesPart = national && (facts.disagreement_states ?? 0) > 1 ? `, in ${fmt(facts.disagreement_states!)} states` : ''
    const against = facts.public_against_meetings
    return {
      kind: 'disagreement',
      template: [`In ${meetingsWord(dis)} ${across} `, P, `, officials ${copy.officials.before}`, T, `${copy.officials.after}.`],
      place,
      basis:
        `Jev (an AI classifier) read the transcripts of ${meetingsWord(facts.lean_meetings ?? 0)} ${where}: ` +
        (against != null ? `the public leaned against in ${fmt(against)}; ` : '') +
        `officials sided against the public in ${fmt(dis)}${statesPart}. A reading of what was said, not a vote count.`,
      ai: true,
    }
  }
  const sp = facts.speakers
  if (sp) {
    const lo = Math.min(sp.for, sp.against)
    const hi = Math.max(sp.for, sp.against)
    if (lo >= SPLIT_MIN_SPEAKERS_PER_SIDE && lo / (lo + hi) >= SPLIT_MIN_MINORITY_SHARE) {
      return {
        kind: 'disagreement',
        template: [P, ' is split on ', T, `: ${fmt(sp.for)} spoke for, ${fmt(sp.against)} against.`],
        place,
        basis: `Counted speakers at local meetings ${where}: ${fmt(sp.for)} for, ${fmt(sp.against)} against, ${fmt(sp.question)} asked a question, ${fmt(sp.neutral)} took no side.`,
        ai: false,
      }
    }
  }

  // 2. Lopsided stance: the story's existing speaker gate, then the public's lean (AI reading).
  const story = STORIES[topicKey]
  if (story?.conclusion && sp) {
    const s = storyConclusion(story, sp, national ? undefined : `in ${label}`)
    if (s) {
      return { kind: 'sentiment', template: [P, ` ${story.conclusion.verb} `, T, '.'], place, basis: s.basis, ai: false }
    }
  }
  const read = facts.lean_meetings ?? 0
  const leans: { n: number | null; words: string; side: string }[] = [
    { n: facts.public_against_meetings, words: 'pushed back on', side: 'against' },
    { n: facts.public_for_meetings, words: 'spoke up for', side: 'for' },
  ]
  for (const l of leans) {
    if (l.n != null && read > 0 && l.n >= PUBLIC_LEAN_MIN_MEETINGS && l.n / read >= PUBLIC_LEAN_MIN_SHARE) {
      return {
        kind: 'sentiment',
        template: ['The public ', `${l.words} `, T, ` in ${meetingsWord(l.n)} in `, P, '.'],
        place,
        basis: `Jev (an AI classifier) read the transcripts of ${meetingsWord(read)} ${where}: the public leaned ${l.side} in ${fmt(l.n)} (${Math.round((100 * l.n) / read)}%). A reading of what was said, not a vote count.`,
        ai: true,
      }
    }
  }

  // 3. Volume with state differences.
  const gap = stateGap(copy, facts, scope)
  if (gap) return gap

  // 4. Plain volume.
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
  // 5. The question.
  return question
}

const COVERAGE = 'Counted from local meeting recordings and transcripts on record; how many meetings are on record varies by state.'

function stateGap(copy: CaptionCopy, facts: TopicCaptionFacts, scope: StoryScope): Caption | null {
  const states = [...facts.states].sort((a, b) => b.meetings - a.meetings || a.state_code.localeCompare(b.state_code))
  const name = (s: { state: string | null; state_code: string }) => s.state ?? s.state_code
  const total = facts.meetings ?? 0

  // City scope: the place against the other places in its state.
  if (scope.city && scope.stateName) {
    const places = facts.places ?? []
    const mine = facts.place ? places.find((p) => p.name === facts.place) : undefined
    const others = places.filter((p) => p !== mine)
    const next = others[0]
    if (!mine || mine.meetings < PLACE_GAP_MIN_MEETINGS || !next || mine.meetings <= next.meetings) return null
    return {
      kind: 'state_gap',
      template: [P, ` ${copy.verb} `, T, ` in ${meetingsWord(mine.meetings)}, more than any other place in ${scope.stateName}.`],
      place: storyScopeLabel(scope),
      basis: `Next: ${next.name}, ${meetingsWord(next.meetings)}. ${COVERAGE}`,
      ai: false,
    }
  }

  // Per resident: only states with a population on record and enough meetings to compare.
  const rated = states
    .filter((s) => s.population != null && s.population > 0 && s.meetings >= PER_CAPITA_MIN_MEETINGS)
    .map((s) => ({ ...s, rate: (s.meetings / s.population!) * 1_000_000 }))
    .sort((a, b) => b.rate - a.rate)
  const perCapita = rated.length >= 2 && rated[0]!.rate >= PER_CAPITA_MIN_RATIO * rated[1]!.rate ? rated[0]! : null
  const perCapitaCaption = (s: NonNullable<typeof perCapita>): Caption => ({
    kind: 'state_gap',
    template: [P, ` ${copy.verb} `, T, ` in ${meetingsWord(s.meetings)}, the most per resident of any state.`],
    place: name(s),
    basis: `${s.rate.toFixed(0)} meetings per million residents, against ${rated[1]!.rate.toFixed(0)} in ${name(rated[1]!)}, the next state with at least ${PER_CAPITA_MIN_MEETINGS} meetings. Population from the jurisdictions on record. ${COVERAGE}`,
    ai: false,
  })

  if (!scope.stateCode) {
    const [top, next] = states
    if (top && next && top.meetings >= STATE_GAP_MIN_MEETINGS && top.meetings >= STATE_GAP_MIN_RATIO * next.meetings) {
      const times = timesWord(top.meetings / next.meetings)
      return {
        kind: 'state_gap',
        template: [P, ` ${copy.verb} `, T, ` in ${meetingsWord(top.meetings)}, ${times ? `more than ${times} any other state` : 'more than any other state'}.`],
        place: name(top),
        basis: `Next: ${name(next)}, ${meetingsWord(next.meetings)}. Of ${meetingsWord(total)} nationwide. ${COVERAGE}`,
        ai: false,
      }
    }
    return perCapita ? perCapitaCaption(perCapita) : null
  }

  // State scope: the state's rank among the states.
  const idx = states.findIndex((s) => s.state_code === scope.stateCode)
  if (idx < 0) return null
  const mine = states[idx]!
  if (mine.meetings < STATE_GAP_MIN_MEETINGS) return perCapita?.state_code === scope.stateCode ? perCapitaCaption(perCapita) : null
  if (idx === 0) {
    const next = states[1]
    if (next && mine.meetings > next.meetings) {
      const times = timesWord(mine.meetings / next.meetings)
      return {
        kind: 'state_gap',
        template: [P, ` ${copy.verb} `, T, ` in ${meetingsWord(mine.meetings)}, ${times ? `more than ${times} any other state` : 'more than any other state'}.`],
        place: storyScopeLabel(scope),
        basis: `Next: ${name(next)}, ${meetingsWord(next.meetings)}. ${COVERAGE}`,
        ai: false,
      }
    }
  }
  if (perCapita?.state_code === scope.stateCode) return { ...perCapitaCaption(perCapita), place: storyScopeLabel(scope) }
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
