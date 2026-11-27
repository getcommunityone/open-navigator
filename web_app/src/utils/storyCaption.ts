// The caption picker (#1125): the one title a topic's record supports for one scope (national, state or city), shared by
// the story header on /stories/<topic>, the home story card and the home Browse Topics tiles.
//
// Rules, in order; each needs its own real counts and otherwise falls through to the next (CLAUDE.md, No Fabricated Data).
// Thresholds and the reasons for them: web_docs/docs/development/story-captions.md.
//   p. position (#1200): the place's conclusion from the AI reading (Jev) of its meetings, in the topic's own words
//      (utils/topicPositions): "[Ohio] mostly favors gun limits.", "[Place] hates [topic]." only for the "hates"
//      topics, else "[Place] is split on [topic].". Since #1234 (owner, 26 Nov 2026) the title is the conclusion only: no
//      count, no "(AI reading)", nothing appended; the count opens the basis line ("The public was against data centers
//      in 283 of 341 meetings where it spoke."). No visible copy says "AI reading"; the map legend discloses the method.
//      Needs at least HATES_MIN_MEETINGS meetings where the public spoke at the scope's level. Below that the rules below
//      run and the basis says how many meetings have a reading so far.
//   a. sentiment ("[Place] hates [topic]." or, for a topic without "hates", "[Place] mostly opposes [topic]."):
//      confident public-against meetings at volume, or (for "hates") the story's counted-speaker gate. The AI's "for"
//      and "mixed" labels are unreliable and never used here, in a count or a ratio.
//   a2/p2. wider_sentiment (#1182) / wider_position (#1200): the place's own reading is too thin, but the broader scope
//      the map colours (its state, then the country) passes (a) or (p). The title is that broader conclusion as the same
//      simple sentence ("America hates data centers.", #1234); the place's own facts open the basis ("Tuscaloosa,
//      Alabama talked about data centers in 2 meetings. …") and the subhead starts with the place.
//   b. disagreement ("[Place] is divided on [topic]."): officials sided against the public at volume, or
//      counted speakers split for and against.
//   c. state_gap: the place leads the other states (or places in its state) by meetings; a near tie names both.
//   d. volume: the place's meeting count.
//   e. question: the topic's question.
// No caption or basis line ever states a zero ("0 spoke for"): a zero clause is left out (owner rule).
import type { TopicCaptionFacts } from '../api/topics'
import { countClauses } from './clauses'
import { STORIES, storyScopeLabel, type StoryScope, type StoryTitlePart } from './dataStory'
import { GENERIC_POSITIONS, hasTopicPositions, positionVerdict, topicPositions, type PositionCounts, type TopicPositions } from './topicPositions'

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
  /** The topic as a story's name on its Start button: "Start the [data center] story". */
  story: string
  /** The pronoun for the topic in a clause after the title ("brought [them] up"). */
  pronoun: 'them' | 'it'
  /**
   * The (a) verb "hates", only for data centers, Flock and license plate readers, and pickleball, where a public against
   * is against the thing. Every other topic says `against` instead (#1182).
   */
  hates?: string
  /**
   * For a topic without "hates" (#1190): what "the public mostly opposed" takes in its (a) title and basis lines, usually
   * the topic ([T]); for gun control, where opposing could mean opposing guns or opposing gun limits (#1126, #1237),
   * "local gun-control measures". Absent (and no `hates`): (a) is skipped.
   */
  opposed?: StoryTitlePart[]
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
    story: 'data center',
    pronoun: 'them',
    facts: 'data-centers',
    verb: 'talked about',
    hates: 'hates',
    officials: { before: 'backed ', after: ' while the public pushed back' },
    question: askMeetings,
  },
  'short-term-rentals': {
    topic: 'short-term rentals',
    story: 'short-term rentals',
    pronoun: 'them',
    opposed: [T],
    facts: 'short-term-rentals',
    verb: 'took up',
    officials: sidedAgainst,
    question: ['Who gets to rent out a home in ', P, '? What meetings said about ', T, '.'],
  },
  flock: {
    topic: 'Flock and license plate readers',
    story: 'Flock and license plate readers',
    pronoun: 'them',
    facts: 'flock',
    verb: 'weighed',
    hates: 'hates',
    officials: sidedAgainst,
    question: ['Who is watching the roads in ', P, '? What meetings said about ', T, '.'],
  },
  'license-plate-readers': {
    topic: 'Flock and license plate readers',
    story: 'Flock and license plate readers',
    pronoun: 'them',
    facts: 'license-plate-readers',
    verb: 'weighed',
    hates: 'hates',
    officials: sidedAgainst,
    question: askMeetings,
  },
  // Shown as "gun control" (#1237): the gun-control question is what the AI reading asks; the slug stays `guns`.
  guns: {
    topic: 'gun control',
    story: 'gun control',
    pronoun: 'it',
    opposed: ['local gun-control measures'],
    facts: 'guns',
    verb: 'took up',
    officials: sidedAgainst,
    question: askMeetings,
  },
  pickleball: {
    topic: 'pickleball',
    story: 'pickleball',
    pronoun: 'it',
    facts: 'pickleball',
    verb: 'brought up',
    hates: 'hates',
    officials: sidedAgainst,
    question: ['Where do the courts go in ', P, '? What meetings said about ', T, '.'],
  },
  'bike-lanes': {
    topic: 'bike lanes',
    story: 'bike lanes',
    pronoun: 'them',
    opposed: [T],
    facts: 'bike-lanes',
    verb: 'took up',
    officials: sidedAgainst,
    question: askMeetings,
  },
  'water-fluoridation': {
    topic: 'water fluoridation',
    story: 'water fluoridation',
    pronoun: 'it',
    opposed: [T],
    facts: 'water-fluoridation',
    verb: 'took up',
    officials: sidedAgainst,
    question: askMeetings,
  },
  // Guides (#1078, #1079): no meeting record backs them yet, so they always ask their question.
  'starting-a-nonprofit': {
    topic: 'a nonprofit',
    story: 'starting a nonprofit',
    pronoun: 'it',
    facts: null,
    verb: 'talked about',
    officials: sidedAgainst,
    question: ['What does it take to start ', T, ' in ', P, '?'],
  },
  insurance: {
    topic: 'insurance',
    story: 'insurance',
    pronoun: 'it',
    facts: null,
    verb: 'talked about',
    officials: sidedAgainst,
    question: ['Are you paying too much for ', T, ' in ', P, '?'],
  },
}

// --- the picker ----------------------------------------------------------------------------------------------------

export type CaptionKind =
  | 'position'
  | 'wider_position'
  | 'disagreement'
  | 'sentiment'
  | 'wider_sentiment'
  | 'state_gap'
  | 'volume'
  | 'question'

export interface Caption {
  kind: CaptionKind
  template: StoryTitlePart[]
  /** How the place blank reads: "America", "Georgia", "Tuscaloosa, Alabama" (or the leading state(s), for a national state_gap). */
  place: string
  /** The line of real numbers under the caption; null for the question. Never states a zero. */
  basis: string | null
  /** True when the caption rests on an AI reading of transcripts (Jev), not counted speakers: the UI labels it. */
  ai: boolean
  /** wider_sentiment / wider_position only: the broader scope the title's claim is about ("America", "Georgia"). */
  widerPlace?: string
  /** position / wider_position only (#1200): the conclusion the title states. */
  verdict?: 'against' | 'for' | 'split'
}

const fmt = (n: number) => n.toLocaleString('en-US')
const meetingsWord = (n: number) => `${fmt(n)} ${n === 1 ? 'meeting' : 'meetings'}`
/** The plain words for the AI meeting reading (#1190): what Jev read in each meeting's transcript. */
const PUBLIC_OPPOSED = 'the public mostly opposed'
/** What "the public mostly opposed" takes for a topic: its own phrase, else the topic itself. */
const opposedObject = (copy: CaptionCopy): StoryTitlePart[] => copy.opposed ?? [T]
const fillTopic = (parts: StoryTitlePart[], topic: string) =>
  parts.map((p) => (typeof p === 'string' ? p : p.blank === 'topic' ? topic : '')).join('')
/** "In 283 meetings across 32 states, the public mostly opposed data centers." (no "AI reading" in visible copy, #1222: the map legend discloses it) */
const opposedBasis = (against: number, where: string, object: string) =>
  `In ${meetingsWord(against)} ${where}, ${PUBLIC_OPPOSED} ${object}.`
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

type Speakers = NonNullable<TopicCaptionFacts['speakers']>

/**
 * "29 speakers counted by hand in 4 states: 18 against and 3 for." (#1134): hand counts always name their scope (they
 * exist in few states, so "nationwide" would overstate them), larger side first, zero sides left out. Questions and no-side
 * speakers are not in the basis.
 */
function speakerBasis(sp: Speakers, where: string, national: boolean): string {
  const total = sp.for + sp.against + sp.question + sp.neutral
  const states = sp.states ?? 0
  const scope = national ? (states > 0 ? ` in ${fmt(states)} ${states === 1 ? 'state' : 'states'}` : '') : ` ${where}`
  const sides = countClauses(
    [
      { n: sp.against, text: (n) => `${fmt(n)} against` },
      { n: sp.for, text: (n) => `${fmt(n)} for` },
    ],
    { leadLarger: true },
  )
  return `${fmt(total)} ${total === 1 ? 'speaker' : 'speakers'} counted by hand${scope}${sides ? `: ${sides}` : ''}.`
}

/**
 * The one title the record supports for `topicKey` (a `CAPTION_COPY` key) in `scope`. `facts` is the caption-facts response
 * for exactly that scope (null while loading or when it failed): with no facts the topic asks its question. Every number in
 * the result comes from `facts`.
 */
export function pickCaption(topicKey: string, facts: TopicCaptionFacts | null | undefined, scope: StoryScope): Caption {
  const copy: CaptionCopy = CAPTION_COPY[topicKey] ?? {
    topic: topicKey.replace(/-/g, ' '),
    story: topicKey.replace(/-/g, ' '),
    pronoun: 'them',
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
  const words = topicPositions(topicKey)

  // (p) The place's conclusion from the AI reading, in the topic's words (#1200).
  const own = positionCounts(facts, facts.meetings)
  if (own) {
    const v = positionVerdict(own, HATES_MIN_MEETINGS[level])
    if (v.kind !== 'too_few') {
      const where2 = national ? 'nationwide' : `in ${label}`
      return {
        kind: 'position',
        template: positionTemplate(copy, words, v, null),
        place,
        // The title is the short conclusion (#1222); its count ("283 of 341 meetings where it spoke") leads the basis.
        basis: `${positionClaim(copy, words, v, null)} ${positionBasis(own, words, where2, dis, facts.lean_meetings)}`,
        ai: true,
        verdict: v.kind === 'majority' ? v.side : 'split',
      }
    }
  }
  // (p2) Too few (or none) of its own: the nearest broader scope with a conclusion, named. It takes (a2)'s place, after
  // the place's own (a) and (b) (counted speakers can still give a place its own title), and only with the new counts:
  // the against-only (a2) would contradict a broader scope that is split.
  const hasPositions = 'public_split_meetings' in facts
  const widerFn = hasPositions ? () => (national ? null : widerPosition(copy, words, facts, own, label, level)) : null
  // Below the floor (or no reading): the rules below keep today's title; the line under it says how many meetings have a
  // reading so far (#1200).
  // An older API without the split and silent counts gets no note (it can't tell none from not sent).
  const readingNote = hasTopicPositions(topicKey) && hasPositions && facts.lean_meetings != null ? readingSoFar(own, facts.meetings ?? null, copy.topic, where, facts.lean_meetings) : null
  const withNote = (c: Caption): Caption =>
    readingNote && c.kind !== 'question' && !c.ai ? { ...c, basis: [c.basis, readingNote].filter(Boolean).join(' ') } : c
  return withNote(pickLegacy(copy, topicKey, facts, scope, { national, level, label, place, where, sp, dis, question, widerFn }))
}

interface LegacyCtx {
  national: boolean
  level: keyof typeof HATES_MIN_MEETINGS
  label: string
  place: string
  where: string
  sp: TopicCaptionFacts['speakers']
  dis: number
  question: Caption
  /** (p2) when the API sends the position counts (#1200); null: the older (a2). */
  widerFn: (() => Caption | null) | null
}

/** Rules (a) to (e), unchanged since #1190: they run when the place has no conclusion from the AI reading. */
function pickLegacy(copy: CaptionCopy, topicKey: string, facts: TopicCaptionFacts, scope: StoryScope, ctx: LegacyCtx): Caption {
  const { national, level, label, place, where, sp, dis, question, widerFn } = ctx

  // (a) "[Place] hates [topic]." / "In 81 meetings, the public mostly opposed [topic]." (#1190)
  const object = opposedObject(copy)
  const stanceVerb = copy.hates ?? (copy.opposed ? 'opposed' : undefined)
  // A topic without "hates" leads with "is divided" (b) when that passes too: its "against" points one way only by the
  // question's wording (#1126), while officials and the public disagreeing needs no direction.
  const dividedFirst = !copy.hates && dis >= DISAGREEMENT_MIN_MEETINGS
  if (stanceVerb && !dividedFirst) {
    const against = facts.public_against_meetings ?? 0
    const story = STORIES[topicKey]
    const gate = story?.conclusion
    const total = sp ? sp.for + sp.against + sp.question + sp.neutral : 0
    const speakersPass = Boolean(
      gate && sp && gate.side === 'against' && total >= gate.minSpeakers && sp.against > 0 && sp.against >= gate.minRatio * sp.for,
    )
    const leanPasses = against >= HATES_MIN_MEETINGS[level]
    // The plain title states the AI count, so it needs the meeting reading itself; "hates" may also rest on counted speakers.
    if (copy.hates ? leanPasses || speakersPass : leanPasses) {
      // Nationally the basis names how many states the meetings span (#1134): "In 283 meetings across 32 states, …".
      const leanStates = facts.public_against_states ?? 0
      const leanWhere = national && leanStates > 1 ? `across ${fmt(leanStates)} states` : where
      const lean = leanPasses ? opposedBasis(against, leanWhere, fillTopic(object, copy.topic)) : ''
      const counted = speakersPass && sp ? speakerBasis(sp, where, national) : ''
      return {
        kind: 'sentiment',
        // The count is in the basis (#1222): the title is the conclusion only.
        template: copy.hates ? [P, ` ${copy.hates} `, T, '.'] : [P, ' mostly opposes ', ...object, '.'],
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
      basis: `In ${meetingsWord(dis)}${span}, officials ${copy.officials.before}${copy.topic}${copy.officials.after}.`,
      ai: true,
    }
  }
  if (sp) {
    const lo = Math.min(sp.for, sp.against)
    const hi = Math.max(sp.for, sp.against)
    if (lo >= SPLIT_MIN_SPEAKERS_PER_SIDE && lo / (lo + hi) >= SPLIT_MIN_MINORITY_SHARE) {
      return { kind: 'disagreement', template: [P, ' is divided on ', T, '.'], place, basis: speakerBasis(sp, where, national), ai: false }
    }
  }

  // (a2) The place's own reading is too thin: the nearest broader scope whose reading passes (a), named (#1182).
  // (p2) replaces it when the API sends the position counts (#1200).
  const wider = widerFn ? widerFn() : stanceVerb ? widerSentiment(copy, facts, label, level, scope.stateName ?? null) : null
  if (wider) return wider

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

// --- (p) position helpers (#1200) ------------------------------------------------------------------------------------

interface LeanFields {
  lean_meetings?: number | null
  public_against_meetings?: number | null
  public_for_meetings?: number | null
  public_split_meetings?: number | null
  public_silent_meetings?: number | null
}

/** The four AI-reading counts, or null when the server doesn't send split and silent (older API) or nothing is read. */
export function positionCounts(f: LeanFields | null | undefined, meetings?: number | null): PositionCounts | null {
  if (!f || f.public_split_meetings == null || f.public_silent_meetings == null) return null
  const against = f.public_against_meetings ?? 0
  const pro = f.public_for_meetings ?? 0
  // "Read" is the sum of the four, so the line under the title adds up: a reading whose label is outside the question's
  // choices (#1201) is in none of them and is not counted as read.
  const read = against + pro + f.public_split_meetings + f.public_silent_meetings
  if (read <= 0) return null
  return { meetings: meetings ?? null, read, against, for: pro, split: f.public_split_meetings, silent: f.public_silent_meetings }
}

type Verdict = Exclude<ReturnType<typeof positionVerdict>, { kind: 'too_few' }>

/**
 * The title for a conclusion (#1222, owner 2026-11-26): the short conclusion sentence only, nothing appended. `who` is the
 * place blank (the scope's own conclusion) or a broader scope's name as literal text (p2, "America hates data centers.").
 * "[California] mostly wants limits on short-term rentals." / "[America] is split on [short-term rentals]."
 */
function positionTemplate(copy: CaptionCopy, words: TopicPositions, v: Verdict, who: string | null): StoryTitlePart[] {
  const name: StoryTitlePart = who ?? P
  if (v.kind === 'split') return [name, ' is split on ', T, '.']
  if (v.side === 'against' && copy.hates) return [name, ` ${copy.hates} `, T, '.']
  const own = v.side === 'against' ? words.againstTitle : words.forTitle
  if (own) return [name, ` ${own}.`]
  return [name, v.side === 'against' ? ' mostly opposes ' : ' mostly supports ', T, '.']
}

/**
 * The conclusion with its count, for the basis line (#1222): the title states no number, so this does. `name` null: the
 * scope's own ("The public was against data centers in 283 of 341 meetings where it spoke."); a name: a broader scope's
 * ("Across America, the public was against …").
 */
function positionClaim(copy: CaptionCopy, words: TopicPositions, v: Verdict, name: string | null): string {
  const lead = name ? `Across ${name}, ` : ''
  const cap = (t: string) => (name ? t : t.charAt(0).toUpperCase() + t.slice(1))
  if (v.kind === 'split') {
    return `${lead}${cap('the public was split on ')}${copy.topic} in the ${meetingsWord(v.of)} where it spoke.`
  }
  if (v.side === 'against' && copy.hates) {
    return `${lead}${cap('the public was against ')}${copy.topic} in ${fmt(v.count)} of ${meetingsWord(v.of)} where it spoke.`
  }
  if (words === GENERIC_POSITIONS) {
    const side = v.side === 'against' ? 'mostly opposed' : 'mostly supported'
    return `${lead}${cap(`the public ${side} `)}${copy.topic} in ${fmt(v.count)} of ${meetingsWord(v.of)} where it spoke.`
  }
  const verb = v.side === 'against' ? words.againstVerb : words.forVerb
  return `${lead}${cap('most meetings ')}${verb}: ${fmt(v.count)} of ${fmt(v.of)} where the public spoke.`
}

/** The place's own meeting count, leading its facts when the title is a broader scope's (#1222). */
function placeCount(copy: CaptionCopy, label: string, m: number | null | undefined): string {
  // An unknown count (null) says nothing: never a made-up zero.
  if (m == null) return ''
  return m > 0 ? `${label} ${copy.verb} ${copy.topic} in ${meetingsWord(m)}.` : `${label} has no meetings on ${copy.topic} on record yet.`
}

/**
 * The line under a conclusion: every count, larger first, no zero stated (#1134). "AI reading of each meeting's transcript:
 * of 225 meetings read in California, the public spoke in 45: 30 were against the cameras, 6 for the cameras and 9 split.
 * In 180 it didn't speak on it."
 */
function positionBasis(c: PositionCounts, words: TopicPositions, where: string, disagreement = 0, leanMeetings?: number | null): string {
  const spoke = c.against + c.for + c.split
  const sides = countClauses(
    [
      { n: c.against, text: (n) => `${fmt(n)} ${words.against.toLowerCase()}` },
      { n: c.for, text: (n) => `${fmt(n)} ${words.for.toLowerCase()}` },
      { n: c.split, text: (n) => `${fmt(n)} split` },
    ],
    { leadLarger: true },
  )
  const parts = [`Of ${meetingsWord(c.read)} read ${where}, the public spoke in ${fmt(spoke)}${sides ? ` (${sides})` : ''}.`]
  if (c.silent > 0) parts.push(`In ${fmt(c.silent)} it didn't speak on it.`)
  // Readings in labels outside the question's choices (#1204) were read, but count in none of the four.
  const lean = Math.max(c.read, leanMeetings ?? c.read)
  if (lean > c.read) parts.push(`${meetingsWord(lean - c.read)} more have a reading in labels this page can't show yet.`)
  const unread = c.meetings != null ? c.meetings - lean : 0
  if (unread > 0) parts.push(`${meetingsWord(unread)} not read yet.`)
  if (disagreement > 0) parts.push(`Officials sided against the public in ${fmt(disagreement)}.`)
  return parts.join(' ')
}

/** How far the reading has got, for the line under a title that has no conclusion yet (#1200). Empty with nothing to say. */
function readingSoFar(c: PositionCounts | null, meetings: number | null, topic: string, where: string, leanMeetings: number | null): string {
  // Readings whose label is outside the question's choices (#1204) are counted in none of the four; say so, never hide them.
  const unusable = Math.max(0, (leanMeetings ?? 0) - (c?.read ?? 0))
  const tail = unusable > 0 ? ` ${meetingsWord(unusable)} more have a reading in labels this page can't show yet.` : ''
  if (!c) return meetings && !unusable ? `No meeting ${where} has a reading of the public's position yet.` : tail.trim()
  const spoke = c.against + c.for + c.split
  const of = meetings != null && meetings >= c.read ? ` of ${fmt(meetings)}` : ''
  const verb = c.read === 1 && !of ? 'has' : 'have'
  const head = `${fmt(c.read)}${of} ${c.read === 1 && !of ? 'meeting' : 'meetings'} ${verb} a reading so far`
  return spoke > 0
    ? `${head}; the public spoke on ${topic} in ${fmt(spoke)}, too few for a conclusion.${tail}`
    : `${head}; in ${c.read === 1 ? 'it' : 'all of them'} the public didn't speak on ${topic}.${tail}`
}

/**
 * (p2): the place's own reading is too thin; the first broader scope (state, then national) with a conclusion leads,
 * named, with the place's own meeting count after it.
 */
function widerPosition(
  copy: CaptionCopy,
  words: TopicPositions,
  facts: TopicCaptionFacts,
  own: PositionCounts | null,
  label: string,
  level: keyof typeof HATES_MIN_MEETINGS,
): Caption | null {
  for (const w of facts.wider ?? []) {
    const c = positionCounts(w)
    if (!c) continue
    const v = positionVerdict(c, HATES_MIN_MEETINGS[w.level])
    if (v.kind === 'too_few') continue
    const name = w.level === 'national' ? 'America' : (w.state ?? w.state_code ?? null)
    if (!name) continue
    const m = facts.meetings
    const spoke = own ? own.against + own.for + own.split : 0
    // The place's own reading as it is; never a zero (owner rule), and nothing when its read failed (null).
    const ownLine = !own
      ? facts.lean_meetings === 0
        ? 'None has been read yet.'
        : ''
      : spoke === 0
        ? `Of its ${meetingsWord(own.read)} read, the public spoke on it in none.`
        : `Of its ${meetingsWord(own.read)} read, the public spoke in ${fmt(spoke)}, under the ${fmt(HATES_MIN_MEETINGS[level])} a conclusion of its own needs.`
    return {
      kind: 'wider_position',
      // The title is the broader scope's simple conclusion (#1222); the place's own facts open the basis.
      template: positionTemplate(copy, words, v, name),
      place: label,
      widerPlace: name,
      basis: [placeCount(copy, label, m), ownLine, positionClaim(copy, words, v, name), positionBasis(c, words, w.level === 'national' ? 'nationwide' : `in ${name}`, 0, w.lean_meetings)].filter(Boolean).join(' '),
      ai: true,
      verdict: v.kind === 'majority' ? v.side : 'split',
    }
  }
  return null
}

/**
 * (a2): the first of the broader scopes in `facts.wider` (state, then national) whose confident public-against meetings
 * pass (a) at that scope's threshold. The title names the broader scope as literal text and keeps the place as its blank,
 * with the place's own meeting count after it.
 */
function widerSentiment(
  copy: CaptionCopy,
  facts: TopicCaptionFacts,
  label: string,
  level: keyof typeof HATES_MIN_MEETINGS,
  stateName: string | null,
): Caption | null {
  const object = opposedObject(copy)
  // What the place's own reading is, stated truly (never "too few" for a place with many readings that aren't against).
  const ownRead = facts.lean_meetings ?? 0
  const ownAgainst = facts.public_against_meetings ?? 0
  const own =
    ownRead === 0
      ? 'None has been read yet.'
      : ownAgainst === 0
        ? `Of its ${meetingsWord(ownRead)} read, none had a public mostly opposed.`
        : `Of its ${meetingsWord(ownRead)} read, ${fmt(ownAgainst)} had a public mostly opposed, under the ${fmt(HATES_MIN_MEETINGS[level])} a title of its own needs.`
  for (const w of facts.wider ?? []) {
    const against = w.public_against_meetings ?? 0
    if (against < HATES_MIN_MEETINGS[w.level]) continue
    const name = w.level === 'national' ? 'America' : (w.state ?? stateName ?? w.state_code ?? null)
    if (!name) continue
    const states = w.public_against_states ?? 0
    const leanWhere = w.level === 'national' ? (states > 1 ? `across ${fmt(states)} states` : 'nationwide') : `in ${name}`
    const m = facts.meetings
    // The title is the broader scope's simple conclusion (#1222); the place's own facts open the basis.
    return {
      kind: 'wider_sentiment',
      template: copy.hates ? [`${name} ${copy.hates} `, T, '.'] : [`${name} mostly opposes `, ...object, '.'],
      place: label,
      widerPlace: name,
      basis: [placeCount(copy, label, m), own, opposedBasis(against, leanWhere, fillTopic(object, copy.topic))].filter(Boolean).join(' '),
      ai: true,
    }
  }
  return null
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
      basis: `Then ${next.name}, ${meetingsWord(next.meetings)}. ${COVERAGE}`,
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
        basis: `Then ${name(next)}, ${meetingsWord(next.meetings)}. Of ${meetingsWord(total)} nationwide. ${COVERAGE}`,
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
        basis: `${third ? `Then ${name(third)}, ${meetingsWord(third.meetings)}. ` : ''}Of ${meetingsWord(total)} nationwide. ${COVERAGE}`,
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
        basis: `Then ${name(next)}, ${meetingsWord(next.meetings)}. ${COVERAGE}`,
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

/**
 * The line under the caption (#1134), about the caption's own scope: the story's national subhead only with the national
 * "hates" caption, otherwise a sentence about the place. Null for the question. States no number (the basis does).
 */
export function captionSubhead(caption: Caption, topicKey: string, scope: StoryScope): string | null {
  const topic = CAPTION_COPY[topicKey]?.topic ?? topicKey.replace(/-/g, ' ')
  const national = !scope.stateName
  const where = national ? '' : ` in ${storyScopeLabel(scope)}`
  switch (caption.kind) {
    case 'position':
      // The national "hates" conclusion keeps the story's own subhead (data centers); otherwise a plain line on the method.
      if (national && caption.verdict === 'against' && CAPTION_COPY[topicKey]?.hates && STORIES[topicKey]?.conclusion?.subhead) {
        return STORIES[topicKey]!.conclusion!.subhead
      }
      return `How the public leaned on ${topic} at local meetings${where}, read from each meeting's transcript.`
    case 'wider_position':
    case 'wider_sentiment':
      // The title is the broader scope's (#1222): the line under it starts with the place in scope, which the home page
      // draws as its place control, and says why the title is the broader one. No number (the basis has them).
      return `${storyScopeLabel(scope)} has too few meetings where the public took a side for a conclusion of its own; the title is ${caption.widerPlace ?? 'the country'}'s.`
    case 'sentiment':
      return national
        ? (STORIES[topicKey]?.conclusion?.subhead ?? null)
        : `At local meetings${where}, the public has mostly spoken against ${topic}.`
    case 'disagreement':
      return `At local meetings${where || ' across the country'}, the public and officials don't always land on the same side of ${topic}.`
    case 'state_gap':
    case 'volume':
      return `Where ${topic} came up at local meetings${where}, in the words said there.`
    default:
      return null
  }
}

/**
 * The Start button's words (#1182): it names the topic and the place in effect, "Start the data center story for Tuscaloosa,
 * Alabama". National (label "National"): no place. `fallback` names a topic with no caption copy (its subject).
 */
export function storyStartLabel(topicKey: string, label: string, fallback?: string): string {
  const raw = CAPTION_COPY[topicKey]?.story ?? fallback ?? topicKey.replace(/-/g, ' ')
  // Lowercase a plain first word ("Homelessness and shelters"), keep a name ("Flock", "ICE").
  const name = /^[A-Z][a-z]/.test(raw) && !CAPTION_COPY[topicKey] ? raw[0]!.toLowerCase() + raw.slice(1) : raw
  return `Start the ${name} story${label && label !== 'National' ? ` for ${label}` : ''}`
}

/** A title past this many characters (a long count title such as "Tuscaloosa, Alabama talked about Flock and license plate
 * readers in 12 meetings.") is set smaller, so it never runs past three lines beside the map (#1182). */
export const LONG_TITLE_CHARS = 60
export const isLongTitle = (t: string) => t.length > LONG_TITLE_CHARS
