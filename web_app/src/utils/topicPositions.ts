// Each topic's position words (#1200): what "for", "against", "split" and "missing" mean for one topic, in the clearest
// plain words, used wherever a topic story shows the public's position (map legend, hover line, data table, the unit
// matrix's "By who spoke" groups, the Overview and the headline).
//
// Every position shown is an AI reading (Jev) of the meeting transcript, never a count of speakers. Which way "for"
// points is fixed per topic by the question Jev was asked: `llm.typesafe.topic_lean.TOPICS[slug].stance` (data centers:
// their own screen, `screen_transcripts`). The words here restate that stance and never invent a direction: for guns,
// "for" is the firearm proposal before the body (a range, a show, a store, a rule or a detection contract), so the words
// are "backed / opposed the gun proposal", never "more gun limits". `topicPositions.test.ts` checks every TOPICS slug is
// here. Decision record: web_docs/docs/development/topic-meeting-lean.md.

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
  /** What "for" means, from topic_lean's stance, for a legend note: "For = allowing short-term rentals". */
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
  // topic_lean: "for" = the firearm-related proposal before the body (a range, show, store, rule or detection contract).
  guns: {
    against: 'Opposed the gun proposal',
    for: 'Backed the gun proposal',
    split: SPLIT,
    silent: SILENT,
    unread: UNREAD,
    againstVerb: 'opposed the gun proposal before them',
    forVerb: 'backed the gun proposal before them',
    againstTitle: 'mostly opposes the gun proposals',
    forTitle: 'mostly backs the gun proposals',
    forMeans: 'For = the proposal before the body (a range, show, store, rule or ShotSpotter contract); against = opposing it',
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

/** The legend's grey, saying which two kinds of missing it holds. */
export const MISSING_LEGEND = `${UNREAD}, or the ${SILENT.charAt(0).toLowerCase()}${SILENT.slice(1)}`

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
