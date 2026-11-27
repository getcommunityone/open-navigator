// Each topic's position words (#1200): what "for", "against", "split" and "missing" mean for one topic, in the clearest
// plain words, used wherever a topic story shows the public's position (map legend, hover line, data table, the unit
// matrix's "By who spoke" groups, the Overview and the headline).
//
// Every position shown is an AI reading (Jev) of the meeting transcript, never a count of speakers. Which way "for"
// points is fixed per topic by the question Jev was asked: `llm.typesafe.topic_lean.TOPICS[slug]` (`subject` and `sides`; data centers:
// their own screen, `screen_transcripts`). The words here restate that stance and never invent a direction. Where "for" and
// "against" could each be read either way, the two sides are named instead (#1237): guns, read by the gun-control
// question (question_version 48468cc5296e), say "Favor gun limits" and "Favor gun rights", never "the gun proposal".
// `topicPositions.test.ts` checks every TOPICS slug is here. Decision record: web_docs/docs/development/topic-meeting-lean.md.

/** One meeting's position in the AI reading. `silent` and `unread` are the two kinds of missing. */
export type PositionKey = 'against' | 'for' | 'split' | 'silent' | 'unread'

export interface TopicPositions {
  /** Legend and table words for a meeting the public mostly opposed (AI reading, P >= 0.7). */
  against: string
  /** Legend and table words for a meeting the public mostly supported (AI reading, P >= 0.7). */
  for: string
  /** The public spoke but was divided, or the AI reading could not tell which way (neutral). */
  split: string
  /** Missing (1 of 2): read, but the public didn't speak on the topic. */
  silent: string
  /** Missing (2 of 2): no AI reading of the meeting yet. */
  unread: string
  /** The headline's predicate after "most meetings that took up [topic]": "wanted limits on short-term rentals". */
  againstVerb: string
  forVerb: string
  /**
   * The short title's predicate after the place (#1222): "[California] mostly wants limits on short-term rentals." Absent:
   * the title says "mostly opposes / mostly supports [topic]".
   */
  againstTitle?: string
  forTitle?: string
  /** What "for" means, from topic_lean's subject and sides, for the map's "How to read this map" note: "For = allowing short-term
   * rentals". A topic with named sides (guns) defines both sides and what isn't counted. No closing period. */
  forMeans: string
}

const SPLIT = 'Split'
const SILENT = "Public didn't speak on it"
const UNREAD = 'No AI reading yet'

export const TOPIC_POSITIONS: Record<string, TopicPositions> = {
  // Data centers' own screen (screen_transcripts): "against" is against the data center.
  'data-centers': {
    against: 'Against data centers',
    for: 'For data centers',
    split: SPLIT,
    silent: SILENT,
    unread: UNREAD,
    againstVerb: 'were against data centers',
    forVerb: 'were for data centers',
    againstTitle: 'mostly opposes data centers',
    forTitle: 'mostly wants data centers',
    forMeans: 'For = for the data center',
  },
  // topic_lean: "for" = allowing short-term rentals (permits, fewer limits); against = banning or restricting them.
  'short-term-rentals': {
    against: 'Want limits on short-term rentals',
    for: 'Want to allow short-term rentals',
    split: SPLIT,
    silent: SILENT,
    unread: UNREAD,
    againstVerb: 'wanted limits on short-term rentals',
    forVerb: 'wanted to allow short-term rentals',
    againstTitle: 'mostly wants limits on short-term rentals',
    forTitle: 'mostly wants to allow short-term rentals',
    forMeans: 'For = allowing short-term rentals; against = banning or restricting them',
  },
  // topic_lean: "for" = buying, keeping or expanding license plate reader cameras; against = rejecting or removing them.
  'license-plate-readers': {
    against: 'Against the cameras',
    for: 'For the cameras',
    split: SPLIT,
    silent: SILENT,
    unread: UNREAD,
    againstVerb: 'were against the plate reader cameras',
    forVerb: 'wanted the plate reader cameras',
    againstTitle: 'mostly opposes the plate reader cameras',
    forTitle: 'mostly wants the plate reader cameras',
    forMeans: 'For = buying, keeping or expanding the cameras; against = rejecting or removing them',
  },
  // Gun control (#1237), read by the gun-control question that wrote the stored readings (question_version 48468cc5296e):
  // mostly_supportive = asking for a limit on firearms (or objecting to a range, shop or show near homes); mostly_opposed =
  // defending gun rights, opposing the limit, or backing a Second Amendment sanctuary resolution. Two named sides, so
  // neither word can be read as "against guns" or "against gun limits".
  guns: {
    against: 'Favor gun rights',
    for: 'Favor gun limits',
    split: SPLIT,
    silent: SILENT,
    unread: 'No reading yet',
    againstVerb: 'favored gun rights',
    forVerb: 'favored gun limits',
    againstTitle: 'mostly favors gun rights',
    forTitle: 'mostly favors gun limits',
    forMeans:
      'Gun limits = a local measure restricting firearms (where they may be carried or fired, sales, ranges or shops near homes, storage). ' +
      'Gun rights = opposing such limits or backing a Second Amendment sanctuary or rights-expansion resolution. ' +
      'Not counted: police service weapons, ShotSpotter, tools called guns',
  },
  // topic_lean: "for" = building, keeping or expanding the pickleball courts or venue.
  pickleball: {
    against: 'Against the courts',
    for: 'For the courts',
    split: SPLIT,
    silent: SILENT,
    unread: UNREAD,
    againstVerb: 'were against the pickleball courts',
    forVerb: 'wanted the pickleball courts',
    againstTitle: 'mostly opposes the pickleball courts',
    forTitle: 'mostly wants the pickleball courts',
    forMeans: 'For = building, keeping or expanding the courts or venue',
  },
  // topic_lean: "for" = keeping or adding fluoride in the water; against = ending or opposing fluoridation.
  'water-fluoridation': {
    against: 'End fluoridation',
    for: 'Keep fluoride in the water',
    split: SPLIT,
    silent: SILENT,
    unread: UNREAD,
    againstVerb: 'wanted fluoridation ended',
    forVerb: 'wanted fluoride kept in the water',
    againstTitle: 'mostly wants fluoridation ended',
    forTitle: 'mostly wants fluoride kept in the water',
    forMeans: 'For = keeping or adding fluoride; against = ending or opposing fluoridation',
  },
  // topic_lean: "for" = building or keeping the bike lanes or paths; against = opposing or removing them.
  'bike-lanes': {
    against: 'Against the bike lanes',
    for: 'For the bike lanes',
    split: SPLIT,
    silent: SILENT,
    unread: UNREAD,
    againstVerb: 'were against the bike lanes',
    forVerb: 'wanted the bike lanes',
    againstTitle: 'mostly opposes the bike lanes',
    forTitle: 'mostly wants the bike lanes',
    forMeans: 'For = building or keeping the lanes or paths',
  },
}
// The home strip's Flock card shares the plate-reader topic.
TOPIC_POSITIONS.flock = TOPIC_POSITIONS['license-plate-readers']!

/** Generic words for a topic with no entry (it has no AI reading question of its own). */
export const GENERIC_POSITIONS: TopicPositions = {
  against: 'Public mostly opposed',
  for: 'Public mostly supported',
  split: SPLIT,
  silent: SILENT,
  unread: UNREAD,
  againstVerb: 'mostly opposed it',
  forVerb: 'mostly supported it',
  forMeans: '',
}

/** The topic's position words, or the generic ones. */
export function topicPositions(slug: string | null | undefined): TopicPositions {
  return (slug && TOPIC_POSITIONS[slug]) || GENERIC_POSITIONS
}

/** True when the topic has its own words (a topic Jev reads with its own stance). */
export const hasTopicPositions = (slug: string | null | undefined) => Boolean(slug && TOPIC_POSITIONS[slug])

/** The legend's grey for one topic's words, saying which two kinds of missing it holds. */
export const missingLegend = (w: Pick<TopicPositions, 'unread' | 'silent'>) =>
  `${w.unread}, or the ${w.silent.charAt(0).toLowerCase()}${w.silent.slice(1)}`

/** The legend's grey, saying which two kinds of missing it holds (the shared words). */
export const MISSING_LEGEND = missingLegend({ unread: UNREAD, silent: SILENT })

/** The legend's note on split, so it is never read as missing. */
export const SPLIT_NOTE = 'Split: the public spoke but was divided, or the AI could not tell which way.'

/** The four AI-reading counts for one place, plus the meetings on record. */
export interface PositionCounts {
  /** Meetings on record in the place (null when not known). */
  meetings?: number | null
  /** Meetings with an AI reading. */
  read: number
  against: number
  for: number
  split: number
  silent: number
}

/** Meetings where the public took a position (for, against or split): the headline's denominator. */
export const spokeOf = (c: PositionCounts) => c.against + c.for + c.split

export type PositionVerdict =
  | { kind: 'majority'; side: 'against' | 'for'; count: number; of: number }
  | { kind: 'split'; of: number }
  | { kind: 'too_few'; of: number }

/**
 * The place's conclusion from its AI reading: a side with more than half of the meetings where the public spoke leads;
 * otherwise the place is split. Below `floor` meetings where the public spoke there is no conclusion (too few).
 */
export function positionVerdict(c: PositionCounts, floor: number): PositionVerdict {
  const of = spokeOf(c)
  if (of < floor || of <= 0) return { kind: 'too_few', of }
  if (c.against * 2 > of) return { kind: 'majority', side: 'against', count: c.against, of }
  if (c.for * 2 > of) return { kind: 'majority', side: 'for', count: c.for, of }
  return { kind: 'split', of }
}

/** One meeting's public position, as the map quote's API gives it (#1230): null when the meeting wasn't read. */
export type QuoteStance = 'against' | 'for' | 'split' | 'silent' | null | undefined

/**
 * The short line under a map quote (#1230): where the public stood at the quoted meeting, in the topic's own words
 * ("Public: <against words>", "Public: Split"); for a read meeting where the public didn't speak on it, "Mentions gun control;
 * no public stance in this meeting"; for a meeting not read yet, only "Mentions gun control". The quote itself is verbatim; this
 * line never restates it.
 */
export function quoteStanceNote(slug: string | null | undefined, subject: string, stance: QuoteStance): string {
  const w = topicPositions(slug)
  if (stance === 'against') return `Public: ${w.against}`
  if (stance === 'for') return `Public: ${w.for}`
  if (stance === 'split') return `Public: ${w.split}`
  if (stance === 'silent') return `Mentions ${subject}; no public stance in this meeting`
  // Not read yet: claim nothing about the public, only that the passage mentions the topic (No Fabricated Data).
  return `Mentions ${subject}`
}

/**
 * The same line for a data-center meeting passage (#1230), from its `ai_public_lean` (data_center_meeting_lean, with a
 * lean under P 0.7 already served as 'mixed'). Only the readings the maps serve are named: a confident "mostly opposed",
 * or no public comment on the data center. "Supported" and "mixed" are audit-only (data-center-meeting-lean.md), so
 * they get no line rather than a claim.
 */
export function dataCenterQuoteNote(aiPublicLean: string | null | undefined): string | null {
  if (aiPublicLean === 'mostly_opposed') return `Public: ${TOPIC_POSITIONS['data-centers']!.against}`
  if (aiPublicLean === 'no_public_comment_on_data_center') return 'Mentions data centers; no public stance in this meeting'
  return null
}
