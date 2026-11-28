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
   * The short title's predicate after the place (#1222): "[California] mostly wants limits on {T}." `{T}` is where the
   * topic control sits in the sentence (#1290, owner 2026-11-27: the topic is the noun in the sentence, never repeated or in
   * brackets). Absent: the title says "mostly opposes / mostly supports [topic]".
   */
  againstTitle?: string
  forTitle?: string
  /** What "for" means, from topic_lean's subject and sides, for the map's "How to read this map" note: "For = allowing short-term
   * rentals". A topic with named sides (guns) defines both sides and what isn't counted. No closing period. */
  forMeans: string
}

const SPLIT = 'Both sides spoke'
const SILENT = "Public didn't speak on it"
const UNREAD = 'Not read yet'

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
    againstTitle: 'mostly opposes {T}',
    forTitle: 'mostly wants {T}',
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
    againstTitle: 'mostly wants limits on {T}',
    forTitle: 'mostly wants to allow {T}',
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
    againstTitle: 'mostly opposes {T}',
    forTitle: 'mostly wants {T}',
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
    againstTitle: 'mostly opposes {T}',
    forTitle: 'mostly favors {T}',
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
    againstTitle: 'mostly opposes the {T} courts',
    forTitle: 'mostly wants the {T} courts',
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
    againstTitle: 'mostly wants {T} ended',
    forTitle: 'mostly wants {T} kept',
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
    againstTitle: 'mostly opposes {T}',
    forTitle: 'mostly wants {T}',
    forMeans: 'For = building or keeping the lanes or paths',
  },
  // speaker_stance (#1391): "for" = slowing traffic (speed humps, lower limits, cameras, crosswalks, stop signs).
  'traffic-safety': {
    against: 'Against the traffic changes',
    for: 'Want traffic slowed',
    split: SPLIT,
    silent: SILENT,
    unread: UNREAD,
    againstVerb: 'were against the traffic changes',
    forVerb: 'wanted traffic slowed',
    againstTitle: 'mostly opposes {T}',
    forTitle: 'mostly wants {T}',
    forMeans: 'For = speed humps, lower limits, speed or red-light cameras, crosswalks or stop signs; against = objecting to them',
  },
  // speaker_stance (#1391): "for" = more police funding, officers or pay; against = cutting or moving police money.
  'police-staffing': {
    against: 'Want less police funding',
    for: 'Want more police funding',
    split: SPLIT,
    silent: SILENT,
    unread: UNREAD,
    againstVerb: 'wanted less police funding',
    forVerb: 'wanted more police funding',
    againstTitle: 'mostly wants less {T}',
    forTitle: 'mostly wants more {T}',
    forMeans: 'For = more officers, a bigger police budget or higher pay; against = cutting or moving police money',
  },
  // speaker_stance (#1391): "for" = spending on parks and recreation (bonds, levies, renovations).
  'parks-funding': {
    against: 'Against the park spending',
    for: 'For the park spending',
    split: SPLIT,
    silent: SILENT,
    unread: UNREAD,
    againstVerb: 'were against the park spending',
    forVerb: 'wanted the park spending',
    againstTitle: 'mostly opposes {T}',
    forTitle: 'mostly wants {T}',
    forMeans: 'For = funding, building or fixing parks or recreation centers; against = objecting to the cost or the project',
  },
  // speaker_stance (#1391): "for" = shelters, services or housing for homeless people; against = objecting to a site or service.
  'homelessness-and-shelters': {
    against: 'Against the shelter or services',
    for: 'For shelters and services',
    split: SPLIT,
    silent: SILENT,
    unread: UNREAD,
    againstVerb: 'were against the shelter or services',
    forVerb: 'wanted shelters and services',
    againstTitle: 'mostly opposes {T}',
    forTitle: 'mostly wants {T}',
    forMeans: 'For = opening or funding a shelter, services or housing for homeless people; against = objecting to a site or service, or wanting camps cleared instead',
  },
  // speaker_stance (#1391): two named sides. "for" = limiting local help to immigration enforcement (sanctuary); against = working with ICE.
  'immigration-and-sanctuary': {
    against: 'Favor working with ICE',
    for: 'Favor sanctuary limits',
    split: SPLIT,
    silent: SILENT,
    unread: UNREAD,
    againstVerb: 'favored working with ICE',
    forVerb: 'favored sanctuary limits',
    againstTitle: 'mostly favors working with ICE on {T}',
    forTitle: 'mostly favors sanctuary limits on {T}',
    forMeans: 'Sanctuary limits = a local policy limiting help to federal immigration enforcement (refusing ICE detainers or 287(g)). Working with ICE = backing that cooperation or ending a sanctuary policy',
  },
  // speaker_stance (#1391): "for" = raising local taxes or fees (a levy, millage or sales tax increase).
  'local-taxation': {
    against: 'Against higher taxes',
    for: 'For the tax or fee increase',
    split: SPLIT,
    silent: SILENT,
    unread: UNREAD,
    againstVerb: 'were against higher taxes',
    forVerb: 'backed the tax or fee increase',
    againstTitle: 'mostly opposes higher {T}',
    forTitle: 'mostly backs higher {T}',
    forMeans: 'For = backing a levy, tax rate or fee increase; against = objecting to higher taxes or fees, or asking for a cut',
  },
  // speaker_stance (#1391): "for" = approving or funding an affordable housing project or policy.
  'affordable-housing': {
    against: 'Against the affordable housing',
    for: 'For the affordable housing',
    split: SPLIT,
    silent: SILENT,
    unread: UNREAD,
    againstVerb: 'were against the affordable housing',
    forVerb: 'wanted the affordable housing',
    againstTitle: 'mostly opposes {T}',
    forTitle: 'mostly wants {T}',
    forMeans: 'For = approving or funding low-income or workforce housing; against = objecting to a project near them',
  },
  // speaker_stance (#1391): "for" = rezoning to allow denser housing (apartments, townhomes, duplexes, ADUs).
  'zoning-regulations': {
    against: 'Against denser zoning',
    for: 'Want more homes allowed',
    split: SPLIT,
    silent: SILENT,
    unread: UNREAD,
    againstVerb: 'were against denser zoning',
    forVerb: 'wanted more homes allowed',
    againstTitle: 'mostly opposes denser {T}',
    forTitle: 'mostly wants denser {T}',
    forMeans: 'For = rezoning to allow apartments, townhomes, duplexes or more homes; against = objecting to density or a rezoning near them',
  },
  // speaker_stance (#1391): "for" = approving a local solar farm, wind project or battery site.
  'renewable-energy': {
    against: 'Against the solar or wind project',
    for: 'For the solar or wind project',
    split: SPLIT,
    silent: SILENT,
    unread: UNREAD,
    againstVerb: 'were against the solar or wind project',
    forVerb: 'wanted the solar or wind project',
    againstTitle: 'mostly opposes {T}',
    forTitle: 'mostly wants {T}',
    forMeans: 'For = backing a solar farm, wind project or battery site; against = objecting to one or asking for a pause',
  },
  // speaker_stance (#1391): "for" = more city security or surveillance cameras in public places.
  'surveillance-cameras': {
    against: 'Against more cameras',
    for: 'For more cameras',
    split: SPLIT,
    silent: SILENT,
    unread: UNREAD,
    againstVerb: 'were against more cameras',
    forVerb: 'wanted more cameras',
    againstTitle: 'mostly opposes {T}',
    forTitle: 'mostly wants {T}',
    forMeans: 'For = new or more public security cameras; against = privacy objections, or removing or limiting cameras',
  },
  // speaker_stance (#1391): "for" = more or better bus or rail service, or transit funding.
  'public-transit': {
    against: 'Against the transit plan',
    for: 'Want more transit',
    split: SPLIT,
    silent: SILENT,
    unread: UNREAD,
    againstVerb: 'were against the transit plan',
    forVerb: 'wanted more transit',
    againstTitle: 'mostly opposes {T}',
    forTitle: 'mostly wants {T}',
    forMeans: 'For = more bus routes, service, light rail or transit funding; against = objecting to a transit project, its cost or a stop near them',
  },
  // speaker_stance (#1391): "for" = approving a liquor license or allowing alcohol sales.
  'alcohol-licensing': {
    against: 'Against the liquor license',
    for: 'For the liquor license',
    split: SPLIT,
    silent: SILENT,
    unread: UNREAD,
    againstVerb: 'were against the liquor license',
    forVerb: 'backed the liquor license',
    againstTitle: 'mostly opposes {T}',
    forTitle: 'mostly wants {T}',
    forMeans: 'For = backing a liquor license or alcohol sales; against = objecting to a bar, liquor store or sales near them',
  },
}
// The home strip's Flock card shares the plate-reader topic.
TOPIC_POSITIONS.flock = TOPIC_POSITIONS['license-plate-readers']!

/** One public speaker's side on a topic (#1391, meeting_speaker_topic_side.side), read by a classifier from their own words. */
export type SpeakerSide = 'for' | 'against' | 'concerns_only' | 'no_position' | 'not_sure'

/**
 * The words for one speaker's side in the topic's own terms: "for" and "against" reuse the topic's position words; a speaker
 * who only raised concerns, took no side, or whose reading was under the confidence floor is said so plainly. Never counted
 * for either side.
 */
export function speakerSideLabel(slug: string | null | undefined, side: SpeakerSide): string {
  const w = topicPositions(slug)
  if (side === 'for') return w.for
  if (side === 'against') return w.against
  if (side === 'concerns_only') return 'Concerns only'
  if (side === 'no_position') return 'No side taken'
  return 'Not sure'
}

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
export const SPLIT_NOTE = 'Both sides spoke: at those meetings the public spoke on both sides, or the AI could not tell which way. This is not neutral.'

/** A single comment or speaker is never "both sides": its shape is a stance_shape chip (components/stance/StanceShapeChip, #1386). */

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
  if (stance === 'split') return `At this meeting: ${w.split.toLowerCase()}`
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
