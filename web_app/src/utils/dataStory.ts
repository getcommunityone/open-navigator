// Pure copy and structure for the data stories (#884). Every sentence is computed from an API response: a figure is stated
// only when the endpoint returned it for the whole scope (never from a capped list), missing data gives a neutral
// description, and nothing here invents a number. Voice: contrasts, counts, rankings, shares and change over time. No causes,
// forecasts, judgments or claims about what people in general think: the records are meeting records, not a survey.
import type {
  AreaConcernsResponse,
  CommunityEventsResponse,
  DataCenterAgendaItemsResponse,
  DataCenterDecisionsResponse,
  DataCenterMeetingMentionsResponse,
  DataCenterPositionsResponse,
  DataCenterProjectsResponse,
  DataCenterSitesResponse,
  JobClaimsResponse,
} from '../api/dataCenters'
import { communityEventKindLabel, concernLabel, siteSourcesText, siteTotal } from '../lib/dataCenterJobs'
import type { StanceQuestion } from '../api/stance'
import { questionText } from './storyQuestion'
import { countClauses, joinClauses } from './clauses'
import {
  DOT_CAP,
  cap,
  chartTitle,
  concernList,
  fmt,
  speakerCounts,
  statusLabel,
  tally,
  where,
  yearOf,
  type ChartData,
  type ChartKey,
  decisionsSentence,
} from './stanceGame'

/** The place a story shows. `city` is only ever set together with a state. */
export interface StoryScope {
  stateCode?: string
  stateName: string | null
  city: string | null
}

export type StoryData = Partial<Record<ChartKey, ChartData | null | undefined>>
export type LoadState = 'loading' | 'error' | 'ready'
export type StoryStatus = Partial<Record<ChartKey, LoadState>>

export interface StoryScreen {
  id: string
  /** The short word above the headline. Never a number. */
  eyebrow: string
  /** The dataset behind the screen's chart, or null for a screen without one. */
  chart: ChartKey | null
  /**
   * `overview` opens the record, `scope` sets the place, `verdict` asks the story's question after the record and shows how
   * readers answered (#950). `question` remains a kind for tests and any legacy screen helper; the story no longer opens on
   * it. `chart` is one dataset.
   */
  kind: 'question' | 'scope' | 'overview' | 'chart' | 'verdict'
  /** "For context": the screen is records about the topic that are not something said in a meeting (sites, projects). */
  kicker?: string
}

/** The Data Center Story: overview first, then voices and the record, then the question at the end (#950). */
export const DATA_CENTER_STORY: StoryScreen[] = [
  { id: 'overview', eyebrow: 'Overview', chart: null, kind: 'overview' },
  { id: 'voices', eyebrow: 'Who spoke up', chart: 'positions', kind: 'chart' },
  { id: 'sites', eyebrow: 'Sites', chart: 'sites', kind: 'chart', kicker: 'For context' },
  { id: 'projects', eyebrow: 'Proposals', chart: 'projects', kind: 'chart', kicker: 'For context' },
  { id: 'jobs', eyebrow: 'Promises', chart: 'job-claims', kind: 'chart' },
  { id: 'concerns', eyebrow: 'Concerns', chart: 'concerns', kind: 'chart' },
  { id: 'meetings', eyebrow: 'Meetings', chart: 'meeting-mentions', kind: 'chart' },
  { id: 'agendas', eyebrow: 'Agendas', chart: 'agenda-items', kind: 'chart' },
  { id: 'decisions', eyebrow: 'Decisions', chart: 'decisions', kind: 'chart' },
  { id: 'gatherings', eyebrow: 'Gatherings', chart: 'community-events', kind: 'chart' },
  { id: 'verdict', eyebrow: 'Your answer', chart: null, kind: 'verdict' },
]

/**
 * Topics with a story. A story needs meeting recordings or transcripts behind it: figure-only data, such as census
 * measures, is shown under Explore, not here. `question` is the story's sentence, for lists (the home page, the hub).
 */
/**
 * A story's conclusion headline (#989): shown only while the national record backs it. `side` is the speakers it claims
 * dominate; the headline shows when that side outnumbers the other by at least `minRatio` among at least `minSpeakers`
 * speakers on record. Otherwise the story's neutral title shows. Decision: development/story-statements-where-you-sit.md.
 */
export interface StoryConclusion {
  headline: string
  /** The verb of the headline with its blanks ("[America] hates [data centers]."), for a title scoped to a place. */
  verb: string
  subhead: string
  side: 'for' | 'against'
  minRatio: number
  minSpeakers: number
  /**
   * The meeting-reading gate (#1134): the headline may also pass on at least this many meetings where Jev read the
   * public as mostly opposed (P >= 0.7). Only the "against" reading is used: hand checks found "supported" and "mixed"
   * unreliable, so no ratio against them is claimed (development/data-center-meeting-lean.md). National, state and
   * single-place (city) gates, since a place has far fewer meetings.
   */
  minLeanMeetings?: { national: number; state: number; city: number }
}

/** Jev's confident readings for the scope (#1134): AI readings of meetings, not counted speakers. */
export interface StoryLean {
  /** Meetings where the public mostly opposed (P >= 0.7). */
  against: number
  /** States with such a meeting, nationally; omitted for a place. */
  states?: number | null
  /** Meetings where officials sided against the public (the #1113 rule). */
  disagreement?: number | null
}

export type StoryLevel = 'national' | 'state' | 'city'

export interface StoryEntry {
  title: string
  topic: string
  pack: string
  question: string
  screens: typeof DATA_CENTER_STORY
  conclusion?: StoryConclusion
}

export const STORIES: Record<string, StoryEntry> = {
  'data-centers': {
    title: 'The Data Center Story',
    topic: 'data centers',
    pack: 'data-centers',
    question: 'What did local meetings say about data centers?',
    screens: DATA_CENTER_STORY,
    conclusion: {
      headline: 'America hates data centers.',
      verb: 'hates',
      subhead:
        "Public comments don't always match America's true sentiment, but our nation is clearly at a fever pitch of data center opposition.",
      side: 'against',
      minRatio: 2,
      minSpeakers: 10,
      minLeanMeetings: { national: 50, state: 10, city: 3 },
    },
  },
}

export type SpeakerCounts = {
  for: number
  against: number
  question: number
  neutral: number
  total?: number
  /** States with any hand-counted speaker, nationally (#1134); omitted for a place. */
  states?: number | null
}

const fmtN = (n: number) => n.toLocaleString('en-US')
const pluralN = (n: number, one: string) => `${fmtN(n)} ${n === 1 ? one : `${one}s`}`
const speakerTotal = (c: SpeakerCounts) => c.total ?? c.for + c.against + c.question + c.neutral

/** "29 speakers counted by hand in 4 states: 18 against, 3 for." (#1134): hand counts always carry their scope. */
function handCountSentence(c: SpeakerCounts, side: 'for' | 'against', placePhrase?: string): string | null {
  const total = speakerTotal(c)
  if (total <= 0) return null
  const states = c.states ?? 0
  const where = placePhrase ? ` ${placePhrase}` : states > 0 ? ` in ${pluralN(states, 'state')}` : ''
  const other = side === 'against' ? 'for' : 'against'
  const sides = countClauses(
    [
      { n: c[side], text: (n) => `${fmtN(n)} ${side}` },
      { n: c[other], text: (n) => `${fmtN(n)} ${other}` },
    ],
    { leadLarger: true },
  )
  return `${pluralN(total, 'speaker')} counted by hand${where}${sides ? `: ${sides}` : ''}.`
}

/**
 * The conclusion to show, with its basis in real counts, or null when the record doesn't back it (#989, #1134). It passes
 * on the meeting reading (`lean`, confident "against" meetings at or above the scope's gate) or on the counted speakers'
 * gate. The basis leads with the meeting reading, labelled as an AI reading, and gives the hand-counted speakers only with
 * their scope ("29 speakers counted by hand in 4 states: 18 against, 3 for.").
 */
export function storyConclusion(
  story: StoryEntry,
  counts: SpeakerCounts | null | undefined,
  /** "in Washington"; omitted for the country. */
  placePhrase?: string,
  lean?: StoryLean | null,
  level: StoryLevel = placePhrase ? 'state' : 'national',
): { headline: string; subhead: string; basis: string } | null {
  const c = story.conclusion
  if (!c) return null
  const total = counts ? speakerTotal(counts) : 0
  const mine = counts ? counts[c.side] : 0
  const other = counts ? (c.side === 'against' ? counts.for : counts.against) : 0
  const speakerPass = Boolean(counts) && total >= c.minSpeakers && mine > 0 && mine >= c.minRatio * other
  const minLean = c.minLeanMeetings?.[level]
  const against = lean && Number.isFinite(lean.against) ? lean.against : 0
  const leanPass = c.side === 'against' && minLean != null && against > 0 && against >= minLean
  if (!speakerPass && !leanPass) return null
  const parts: string[] = []
  if (leanPass) {
    const states = lean?.states ?? 0
    const where = placePhrase ? ` ${placePhrase}` : states > 0 ? ` across ${pluralN(states, 'state')}` : ''
    parts.push(`The public mostly opposed ${story.topic} in ${pluralN(against, 'meeting')}${where}.`)
  }
  const hand = counts ? handCountSentence(counts, c.side, placePhrase) : null
  if (hand) parts.push(hand)
  return { headline: c.headline, subhead: c.subhead, basis: parts.join(' ') }
}

export type StoryTitlePart = string | { blank: 'place' | 'topic' }

/** The national meeting reading from positions `lean_totals` (#1134), or null when it isn't served. */
export function nationalLean(res: DataCenterPositionsResponse | null | undefined): StoryLean | null {
  const t = res?.available ? res.lean_totals : null
  if (!t) return null
  return { against: t.public_against_meetings ?? 0, states: t.public_against_states ?? 0, disagreement: t.disagreement_meetings ?? 0 }
}

/** States with at least one hand-counted speaker in positions `by_state` (#1134), counted from the data. */
export function speakerStateCount(res: DataCenterPositionsResponse | null | undefined): number {
  const rows = res?.available ? (res.by_state ?? []) : []
  return rows.filter((r) => (r.speakers_for ?? 0) + (r.speakers_against ?? 0) + (r.speakers_question ?? 0) + (r.speakers_neutral ?? 0) > 0).length
}

/** Screen ids that were renamed: an old link still lands on the screen that replaced it. */
// 'scope' (Where) folded into the Overview, whose title carries the place picker (#1134).
const SCREEN_ALIASES: Record<string, string> = { turn: 'verdict', question: 'overview', scope: 'overview' }

/** The position of the screen a `?screen=` value names, or -1. */
export function storyScreenIndex(screens: ReadonlyArray<{ id: string }>, param: string | null | undefined): number {
  if (!param) return -1
  const id = SCREEN_ALIASES[param] ?? param
  return screens.findIndex((s) => s.id === id)
}

/** Every dataset the story reads. */
export const STORY_CHARTS: ChartKey[] = DATA_CENTER_STORY.flatMap((s) => (s.chart ? [s.chart] : []))

/** "Tuscaloosa, Alabama" / "Alabama" / "National": exactly what the story shows. */
export function storyScopeLabel(scope: StoryScope): string {
  if (!scope.stateName) return 'National'
  return scope.city ? `${scope.city}, ${scope.stateName}` : scope.stateName
}

/**
 * One extra context line for a concerns round whose statement is about land use: how often land and property concerns appear in
 * the same data. Null unless that category is really in the data for the scope (never a placeholder).
 */
export function landConcernNote(res: AreaConcernsResponse | null | undefined, place: string | null): string | null {
  if (!res) return null
  const list = concernList(res, place) ?? []
  const total = list.reduce((a, c) => a + c.mention_count, 0)
  const land = list.find((c) => c.concern === 'land')
  if (!land || land.mention_count <= 0 || total <= 0) return null
  return `${cap(concernLabel('land'))} appear in ${fmt(land.mention_count)} of ${plural(total, 'concern mention')} (${Math.round((100 * land.mention_count) / total)}%).`
}

/** Where a "For context" screen's figures come from (they are not from meeting recordings or transcripts), or null. */
export function contextSourceFor(key: string | null | undefined): string | null {
  if (key === 'sites') return 'Epoch AI and the US Data Center Registry'
  if (key === 'projects') return 'curated announcements and Epoch AI'
  return null
}

/** The place as it reads in "What did local meetings in ___ say about ...?": "the United States", "Alabama" or "Tuscaloosa, Alabama". */
export function storyPlaceDisplay(scope: StoryScope): string {
  return scope.stateName ? storyScopeLabel(scope) : 'the United States'
}

/**
 * The scope one chart really shows. Sites carry no city (the source has none), so with a city chosen the sites screen shows
 * the state and says so.
 */
export function chartScopeLabel(key: string, scope: StoryScope): string {
  if (key === 'sites' && scope.city) return scope.stateName ?? 'National'
  return storyScopeLabel(scope)
}

/** The place name a sentence uses (`null` is national). */
function placeFor(key: string, scope: StoryScope): string | null {
  const label = chartScopeLabel(key, scope)
  return label === 'National' ? null : label
}

const plural = (n: number, one: string, many = `${one}s`) => `${fmt(n)} ${n === 1 ? one : many}`
const lower = (s: string) => s.charAt(0).toLowerCase() + s.slice(1)

// --- the row of large counts --------------------------------------------------------------------------------------

export interface StoryStat {
  key: string
  value: number
  label: string
}

/**
 * Real whole-scope counts from the endpoints' own totals. A count that is missing, zero or not loaded is left out. Under a city
 * scope a count the source cannot narrow to a city (sites) keeps its own, wider scope in its label ("data center sites in
 * Alabama") instead of passing for a city figure; `statsScopeNote` says so under the row.
 */
export function storyStats(data: StoryData, scope: StoryScope = { stateName: null, city: null }): StoryStat[] {
  const mentions = data['meeting-mentions'] as DataCenterMeetingMentionsResponse | null | undefined
  const agendas = data['agenda-items'] as DataCenterAgendaItemsResponse | null | undefined
  const sites = data.sites as DataCenterSitesResponse | null | undefined
  const claims = data['job-claims'] as JobClaimsResponse | null | undefined
  const projects = data.projects as DataCenterProjectsResponse | null | undefined
  const k = sites?.counts
  const sitesOnRecord = siteTotal(k)
  // Counts from meeting recordings and transcripts lead; counts from other sources follow with their source named.
  const all: StoryStat[] = [
    { key: 'meetings', value: mentions?.counts?.meetings ?? 0, label: 'meetings where a data center came up' },
    { key: 'passages', value: mentions?.counts?.passages ?? 0, label: 'meeting passages quoted' },
    { key: 'agendas', value: agendas?.counts ? agendas.counts.upcoming + agendas.counts.past : 0, label: 'meeting agendas that name a data center' },
    { key: 'claims', value: (claims?.totals?.construction ?? 0) + (claims?.totals?.operations ?? 0), label: 'jobs claims made in meetings' },
    { key: 'sites', value: sitesOnRecord, label: `data center sites on record${scope.city && scope.stateName ? ` in ${scope.stateName}` : ''}, from ${siteSourcesText(sites?.items, sitesOnRecord) ?? 'Epoch AI'}` },
    { key: 'projects', value: projects?.total ?? 0, label: 'data center projects on record, from announcements and Epoch AI' },
  ]
  return all.filter((s) => s.value > 0)
}

/** The note under a row of counts: which place they are for, and which of them are wider than that. */
export function statsScopeNote(stats: StoryStat[], scope: StoryScope): string {
  const label = scope.stateName ? storyScopeLabel(scope) : 'the whole country'
  if (scope.city && scope.stateName && stats.some((s) => s.key === 'sites')) {
    return `Counts for ${label}, except sites: those are listed by state, so that count is for ${scope.stateName}.`
  }
  return `Counts for ${label}.`
}

// --- headline and context per screen ------------------------------------------------------------------------------

export interface ScreenText {
  headline: string
  /** One line of context, ending in a question when the next screen answers it. */
  context: string
  /** Nothing in scope for this screen: the screen offers to broaden. */
  empty: boolean
  /** The data could not be loaded (not the same as empty). */
  failed: boolean
}

const noData = (scope: StoryScope): ScreenText => ({
  headline: scope.stateName ? 'No data available for this place.' : 'No data available.',
  context: scope.stateName
    ? `Nothing is on record here for ${storyScopeLabel(scope)}. Try a wider place.`
    : 'Nothing is on record here yet.',
  empty: true,
  failed: false,
})

// --- who spoke up (#930) ---------------------------------------------------------------------------------------------

/** One of the five figures that lead the hub and the "Who spoke up" screen. `value` null reads "not recorded", with `reason`. */
export interface PositionFigure {
  key: 'for' | 'against' | 'question' | 'votes_for' | 'votes_against'
  label: string
  value: number | null
  reason: string | null
}

export const VOTES_NOT_RECORDED = 'Votes were not recorded for these decisions.'
export const SPEAKERS_NOT_RECORDED = 'No public comment on a data center item is on record for these meetings.'
/** Meetings were reviewed and none had a speaker on a data center item (#1059): the count is a real 0, said plainly. */
export function speakersNoneFound(reviewed: number, scope?: StoryScope | null): string {
  const place = scope?.stateName ? ` in ${storyScopeLabel(scope)}` : ''
  return reviewed === 1
    ? `The 1 meeting reviewed${place} had no public speaker on a data center item.`
    : `None of the ${fmt(reviewed)} meetings reviewed${place} had a public speaker on a data center item.`
}
/** The one quiet line the hub and the story show while the table behind these figures is not in the database. */
export const POSITIONS_NOT_LOADED = 'Who spoke for and against is not loaded yet.'

/** The table is in the database and answered (it may still hold nothing for the place). */
export function positionsLoaded(res: DataCenterPositionsResponse | null | undefined): res is DataCenterPositionsResponse {
  return Boolean(res && res.available === true && res.totals)
}

/**
 * The five figures, or null when the table is not loaded. Speakers are 0 when meetings were reviewed and none had a speaker
 * on a data center item (said so in the reason, #1059), and null ("not recorded") only when no meeting in scope was
 * reviewed. Votes are null when no decision recorded a tally. A real 0 beside real counts stays 0.
 */
export function positionFigures(
  res: DataCenterPositionsResponse | null | undefined,
  scope?: StoryScope | null,
): PositionFigure[] | null {
  if (!positionsLoaded(res)) return null
  const t = res.totals
  const c = speakerCounts(res)
  const tallies = t.decisions_with_tally ?? 0
  const reviewed = t.meetings_reviewed ?? 0
  const vote = (v: number | null) => (tallies > 0 && v != null ? v : null)
  // Reviewed meetings with no speaker found are a real 0 (#1059); "not recorded" only when nothing was reviewed.
  const sp = (v: number | undefined) => (c ? (v ?? 0) : reviewed > 0 ? 0 : null)
  const spReason = c ? null : reviewed > 0 ? speakersNoneFound(reviewed, scope) : SPEAKERS_NOT_RECORDED
  const voReason = tallies > 0 ? null : VOTES_NOT_RECORDED
  return [
    { key: 'for', label: 'spoke for', value: sp(c?.for), reason: spReason },
    { key: 'against', label: 'spoke against', value: sp(c?.against), reason: spReason },
    { key: 'question', label: 'asked a question', value: sp(c?.question), reason: spReason },
    { key: 'votes_for', label: 'votes for', value: vote(t.votes_for), reason: voReason },
    { key: 'votes_against', label: 'votes against', value: vote(t.votes_against), reason: voReason },
  ]
}

/** A figure as it reads: the count, or "—" when it is not available yet (never a made-up 0, #1289). */
export function figureDisplay(v: number | null | undefined): string {
  return v == null ? '—' : fmt(v)
}

/**
 * The line under the figures: what they count, where, and how many meetings and decisions they come from. With nobody
 * speaking it says so (#1289): never "From 1 meeting", which counted the meeting with the vote and read as if someone spoke.
 */
export function positionsCaption(res: DataCenterPositionsResponse | null | undefined, scope: StoryScope): string | null {
  if (!positionsLoaded(res)) return null
  const t = res.totals
  const label = scope.stateName ? storyScopeLabel(scope) : null
  const place = label ? `in ${label}` : 'across the country'
  const tallies = t.decisions_with_tally ?? 0
  const reviewed = t.meetings_reviewed ?? 0
  if (!speakerCounts(res)) {
    const votes = tallies > 0 ? ` Votes from ${plural(tallies, 'decision')} with a recorded vote.` : ''
    if (reviewed > 0) return `No public speakers in the ${plural(reviewed, 'meeting')} reviewed ${place}.${votes}`
    return `Public speakers are not available yet for ${label ?? 'the country'}: no meeting here has been reviewed.${votes}`
  }
  const from: string[] = []
  if ((t.meetings ?? 0) > 0) from.push(plural(t.meetings!, 'meeting'))
  if (tallies > 0) from.push(`${plural(tallies, 'decision')} with a recorded vote`)
  return `Speakers at local meetings ${place} where a data center item was discussed.${from.length ? ` From ${from.join(' and ')}.` : ''}`
}

/**
 * "Of 6 people who spoke on a data center item at local meetings in Texas, 2 spoke for it and 1 against." (#1134): zero sides
 * are left out and the larger side leads; with no one for or against, it says only how many spoke.
 */
export function speakersHeadline(c: { for: number; against: number; total: number }, place: string | null): string {
  const sides = [
    { n: c.for, side: 'for' },
    { n: c.against, side: 'against' },
  ]
    .filter((x) => x.n > 0)
    .sort((a, b) => b.n - a.n)
  const lead = `${plural(c.total, 'person', 'people')} who spoke on a data center item at local meetings ${where(place)}`
  if (sides.length === 0) return `${lead.charAt(0).toUpperCase()}${lead.slice(1)}.`.replace(' who spoke on', ' spoke on')
  const clauses = joinClauses(sides.map((x, i) => (i === 0 ? `${fmt(x.n)} spoke ${x.side} it` : `${fmt(x.n)} ${x.side}`)))
  return `Of ${lead}, ${clauses}.`
}

function positionsText(res: DataCenterPositionsResponse, scope: StoryScope): ScreenText {
  const title = 'Who spoke up about data centers'
  if (!positionsLoaded(res)) return { headline: title, context: POSITIONS_NOT_LOADED, empty: false, failed: false }
  const c = speakerCounts(res)
  const t = res.totals
  const place = placeFor('positions', scope)
  const tallies = t.decisions_with_tally ?? 0
  // No zero clause in a title (#1134): "Recorded votes: 5 for, in 1 decision.", never "and 0 against".
  const voteSides =
    tallies > 0 && t.votes_for != null && t.votes_against != null
      ? countClauses([
          { n: t.votes_for, text: (n) => `${fmt(n)} for` },
          { n: t.votes_against, text: (n) => `${fmt(n)} against` },
        ])
      : ''
  const votes = voteSides ? `Recorded votes: ${voteSides}, in ${plural(tallies, 'decision')}.` : null
  if (!c) {
    if (!votes) {
      return noData(scope)
    }
    // Votes only: the figures beside the headline say why the speaker counts are not recorded.
    return { headline: `${votes.replace(/\.$/, '')} ${where(place)}.`, context: 'How often does it come up?', empty: false, failed: false }
  }
  const headline = speakersHeadline(c, place)
  // Questions and no-side speakers go in the context line, only when there are any (#1134).
  const others = countClauses([
    { n: c.question, text: (n) => `${fmt(n)} asked a question` },
    { n: c.neutral, text: (n) => `${fmt(n)} took no side` },
  ])
  const rest = others ? `${others.charAt(0).toUpperCase()}${others.slice(1)}. ` : ''
  // With no recorded tally the figures say so once ("not recorded", with the reason); the line here does not repeat it.
  return { headline, context: `${rest}${votes ? `${votes} ` : ''}How often does it come up?`, empty: false, failed: false }
}

function sitesText(res: DataCenterSitesResponse, scope: StoryScope): ScreenText | null {
  const k = res.counts
  if (!k) return null
  const total = siteTotal(k)
  if (total <= 0) return null
  const place = placeFor('sites', scope)
  const pipeline = k.planned + k.under_construction
  const headline =
    k.operating === 0
      ? `None of the ${plural(total, 'data center site')} ${where(place)} ${total === 1 ? 'is' : 'are'} listed as operating; ${fmt(pipeline)} ${pipeline === 1 ? 'is' : 'are'} planned or under construction.`
      : `Of ${plural(total, 'data center site')} ${where(place)}, ${fmt(k.operating)} ${k.operating === 1 ? 'is' : 'are'} operating, and ${fmt(pipeline)} more ${pipeline === 1 ? 'is' : 'are'} planned or under construction.`
  const rest: string[] = []
  if ((k.cancelled ?? 0) > 0) rest.push(`${fmt(k.cancelled ?? 0)} cancelled, per the source`)
  if (k.no_longer_listed > 0) rest.push(`${fmt(k.no_longer_listed)} no longer listed`)
  if (k.status_not_published > 0) rest.push(`${fmt(k.status_not_published)} with no published status`)
  const lead = rest.length ? `Also on record: ${rest.join(' and ')}. ` : ''
  const byState = scope.city ? `Sites are listed by state, so this is ${scope.stateName}. ` : ''
  return { headline, context: `${lead}${byState}What is proposed?`, empty: false, failed: false }
}

function projectsText(res: DataCenterProjectsResponse, scope: StoryScope): ScreenText | null {
  const items = res.items ?? []
  if (items.length === 0) return null
  const place = placeFor('projects', scope)
  const total = Math.max(res.total ?? 0, items.length)
  const t = tally(items, (p) => statusLabel(p.status))
  const phrase = (k: string) => (k === 'Status not published' ? 'with no published status' : `listed as ${lower(k)}`)
  const top = t[0]!
  const second = t[1]
  const complete = total <= items.length
  const headline = complete
    ? `Of ${plural(total, 'data center project')} on record ${where(place)}, ${fmt(top.count)} ${top.count === 1 ? 'is' : 'are'} ${phrase(top.key)}${second ? ` and ${fmt(second.count)} ${phrase(second.key)}` : ''}.`
    : `Of ${plural(total, 'data center project')} on record ${where(place)}, ${fmt(items.length)} ${items.length === 1 ? 'is' : 'are'} listed here, and ${fmt(top.count)} of those ${top.count === 1 ? 'is' : 'are'} ${phrase(top.key)}.`
  return {
    headline,
    context: `${complete ? '' : `The figure shows the ${fmt(items.length)} listed. `}What gets promised in meetings?`,
    empty: false,
    failed: false,
  }
}

/** No claims on record: the screen leads with actual payroll jobs (BLS QCEW, #1019) when they are published. */
function payrollText(res: JobClaimsResponse, scope: StoryScope): ScreenText | null {
  const rows = res.employment ?? []
  const own = rows.find((r) => r.area_level === 'state') ?? rows.find((r) => r.area_level === 'national')
  if (!own || !own.disclosed || own.employment == null) return null
  const where = own.area_level === 'national' ? 'Across the U.S.,' : `In ${own.area_name},`
  const cityNote = scope.city && own.area_level === 'state' ? ` BLS counts by county and state, not city, so this is ${own.area_name}.` : ''
  const pct = own.employment_change_pct
  return {
    headline: `${where} ${fmt(own.employment)} people worked on payroll in the industry that includes data centers in ${own.year}.`,
    context: `${pct != null ? `That is ${pct > 0 ? 'up' : pct < 0 ? 'down' : 'unchanged'}${pct ? ` ${Math.abs(pct)}%` : ''} from the year before. ` : ''}No jobs promises are on record in meetings here yet.${cityNote} What concerns come up?`,
    empty: false,
    failed: false,
  }
}

function jobsText(res: JobClaimsResponse, scope: StoryScope): ScreenText | null {
  const c = res.totals?.construction ?? 0
  const o = res.totals?.operations ?? 0
  if (c + o <= 0) return payrollText(res, scope)
  const place = placeFor('job-claims', scope)
  // No zero clause (#1134): a side with no claims is left out of the title.
  const headline = `Meetings ${where(place)} include ${countClauses([
    { n: c, text: (n) => `${plural(n, 'claim')} about construction jobs` },
    { n: o, text: (n) => `${plural(n, 'claim')} about operations jobs` },
  ])}.`
  const gap = Math.abs(c - o)
  const lead = c > 0 && o > 0 && gap > 0 ? `${c > o ? 'Construction' : 'Operations'} claims outnumber ${c > o ? 'operations' : 'construction'} claims by ${fmt(gap)}. ` : ''
  return {
    headline,
    context: `${lead}Each one was said in a local meeting. What concerns come up?`,
    empty: false,
    failed: false,
  }
}

/** "a", "a and b", "a, b and c". */
const andList = (xs: string[]) => (xs.length <= 1 ? (xs[0] ?? '') : `${xs.slice(0, -1).join(', ')} and ${xs[xs.length - 1]}`)

/** Concerns with mentions, one per concern (rows for the same concern are merged), most mentioned first. */
function rankedConcerns(list: Array<{ concern: string; mention_count: number; jurisdictions?: string[] | null }>) {
  const m = new Map<string, { concern: string; mention_count: number; jurisdictions: string[] }>()
  for (const c of list) {
    if (!(c.mention_count > 0)) continue
    const prev = m.get(c.concern)
    const towns = [...(prev?.jurisdictions ?? []), ...(c.jurisdictions ?? [])]
    m.set(c.concern, { concern: c.concern, mention_count: (prev?.mention_count ?? 0) + c.mention_count, jurisdictions: [...new Set(towns)].sort() })
  }
  return [...m.values()].sort((a, b) => b.mention_count - a.mention_count || a.concern.localeCompare(b.concern))
}

/** "Nationally, traffic leads, then water, then land and property." from the real national rows; null when there are none. */
export function nationalConcernNote(res: AreaConcernsResponse | null | undefined): string | null {
  const nat = rankedConcerns(res?.national ?? [])
  if (nat.length === 0) return null
  const lead = nat.filter((c) => c.mention_count === nat[0]!.mention_count)
  const rest = nat.slice(lead.length, Math.max(3, lead.length + 1)).map((c) => concernLabel(c.concern))
  const head = `Nationally, ${andList(lead.map((c) => concernLabel(c.concern)))} ${lead.length > 1 ? 'lead' : 'leads'}`
  return `${head}${rest.length ? `, then ${rest.join(', then ')}` : ''}.`
}

function concernsText(res: AreaConcernsResponse, scope: StoryScope): ScreenText | null {
  const place = placeFor('concerns', scope)
  const sorted = rankedConcerns(concernList(res, place) ?? [])
  const total = sorted.reduce((a, c) => a + c.mention_count, 0)
  if (sorted.length === 0 || total <= 0) return null
  const records = !place ? 'in meeting records nationally' : scope.city ? `in meeting records in ${place}` : `in ${place} meeting records`
  const top = sorted[0]!
  const tied = sorted.filter((c) => c.mention_count === top.mention_count)
  const pct = Math.round((100 * top.mention_count) / total)
  const name = concernLabel(top.concern)
  let headline: string
  if (sorted.length === 1) {
    // The towns are named only for a state: under a city they would repeat the place.
    const towns = scope.city ? [] : top.jurisdictions
    const shown = towns.length > 3 ? [...towns.slice(0, 3), plural(towns.length - 3, 'other place')] : towns
    headline = `${cap(name)} was the only concern raised ${records}: ${plural(top.mention_count, 'mention')}${shown.length ? `, in ${andList(shown)}` : ''}.`
  } else if (tied.length > 1) {
    headline = `${cap(andList(tied.map((c) => concernLabel(c.concern))))} are tied as the most raised concerns ${records}: ${plural(top.mention_count, 'mention')} each, of ${fmt(total)}.`
  } else {
    const second = sorted[1]!
    const next = sorted.filter((c) => c.mention_count === second.mention_count)
    headline = `${cap(name)} is raised most ${records}: ${fmt(top.mention_count)} of ${plural(total, 'mention')} (${pct}%), ahead of ${andList(next.map((c) => concernLabel(c.concern)))} with ${fmt(second.mention_count)}${next.length > 1 ? ' each' : ''}.`
  }
  const national = place ? nationalConcernNote(res) : null
  return {
    headline,
    context: `${national ? `${national} ` : ''}These count passages in meeting transcripts, not people. When does it come up?`,
    empty: false,
    failed: false,
  }
}

function meetingsText(res: DataCenterMeetingMentionsResponse, scope: StoryScope): ScreenText | null {
  const items = res.items ?? []
  const passages = res.counts?.passages ?? 0
  const meetings = res.counts?.meetings ?? 0
  if (items.length === 0 && passages <= 0) return null
  const place = placeFor('meeting-mentions', scope)
  // The timeline's year (#1140): only from a complete list, so "most of them" is a real count of distinct meetings.
  const byYearMeetings = new Map<string, Set<string>>()
  if (passages > 0 && items.length >= passages) {
    for (const m of items) {
      const y = yearOf(m.meeting_date)
      if (y) byYearMeetings.set(y, (byYearMeetings.get(y) ?? new Set()).add(m.video_id))
    }
  }
  const ranked = [...byYearMeetings.entries()].sort((a, b) => b[1].size - a[1].size || b[0].localeCompare(a[0]))
  const peak = ranked[0]
  const tied = ranked.length > 1 && ranked[1]![1].size === peak![1].size
  const peakPhrase = peak && byYearMeetings.size > 1 && !tied ? (peak[1].size * 2 > meetings ? `most of them in ${peak[0]}` : `the most in ${peak[0]}`) : null
  const headline =
    meetings > 0 && passages > 0 && peakPhrase
      ? `Data centers came up in ${plural(meetings, 'meeting')} ${where(place)}, ${peakPhrase} (${plural(passages, 'quoted passage')}).`
      : meetings > 0 && passages > 0
      ? `A data center came up in ${plural(meetings, 'meeting')} ${where(place)}, in ${plural(passages, 'quoted passage')}.`
      : passages > 0
        ? `Meeting passages that mention a data center ${where(place)} number ${fmt(passages)}.`
        : `Meeting passages that mention a data center ${where(place)} number ${fmt(items.length)}.`
  const years = tally(items, (m) => yearOf(m.meeting_date)).sort((a, b) => a.key.localeCompare(b.key))
  let lead = ''
  const complete = passages > 0 && items.length >= passages
  if (years.length >= 2 && complete) {
    const a = years[0]!
    const z = years[years.length - 1]!
    lead = `By year of the meeting: ${plural(a.count, 'passage')} in ${a.key}, ${plural(z.count, 'passage')} in ${z.key}. `
  } else if (years.length >= 1) {
    const top = [...years].sort((a, b) => b.count - a.count || b.key.localeCompare(a.key))[0]!
    lead = `Among the ${items.length >= DOT_CAP || (passages > items.length) ? `most recent ${fmt(items.length)} passages` : `${fmt(items.length)} passages`}, ${top.key} has the most (${fmt(top.count)}). `
  }
  return { headline, context: `${lead}What is on the agenda?`, empty: false, failed: false }
}

function agendasText(res: DataCenterAgendaItemsResponse, scope: StoryScope): ScreenText | null {
  const u = res.counts?.upcoming ?? 0
  const p = res.counts?.past ?? 0
  if (u + p <= 0) return null
  const place = placeFor('agenda-items', scope)
  const headline =
    u > 0
      ? `Of ${plural(u + p, 'meeting agenda')} that ${u + p === 1 ? 'names' : 'name'} a data center ${where(place)}, ${fmt(u)} ${u === 1 ? 'is' : 'are'} for upcoming meetings and ${fmt(p)} for past ones.`
      : `None of the ${plural(p, 'meeting agenda')} that ${p === 1 ? 'names' : 'name'} a data center ${where(place)} is for an upcoming meeting.`
  return {
    headline,
    context: 'Upcoming means the meeting date has not passed. What did the meetings decide?',
    empty: false,
    failed: false,
  }
}

export const DECISIONS_NOT_LOADED = 'Decisions on data center items are not loaded yet.'

function decisionsText(res: DataCenterDecisionsResponse, scope: StoryScope): ScreenText | null {
  const c = res.counts?.contested ?? 0
  const u = res.counts?.uncontested ?? 0
  if (c + u <= 0) return null
  return {
    headline: decisionsSentence(c, u, placeFor('decisions', scope)),
    context: 'Without debate means on the consent agenda or by a routine vote, and includes items that were tabled or denied. What about meetings the companies host?',
    empty: false,
    failed: false,
  }
}

function gatheringsText(res: CommunityEventsResponse, scope: StoryScope): ScreenText | null {
  const items = res.items ?? []
  if (items.length === 0) return null
  const place = placeFor('community-events', scope)
  const kinds = tally(items, (e) => e.event_kind)
  const phrase = (k: { key: string; count: number }) => {
    const label = lower(communityEventKindLabel(k.key))
    return `${fmt(k.count)} ${k.count === 1 ? label : `${label}s`}`
  }
  const shown = kinds.slice(0, 2)
  const other = kinds.slice(2).reduce((a, k) => a + k.count, 0)
  const atLeast = items.length >= DOT_CAP ? 'at least ' : ''
  const parts = shown.map(phrase)
  const named = other > 0 ? `${parts.join(', ')} and ${fmt(other)} of other kinds` : parts.length === 2 ? `${parts[0]} and ${parts[1]}` : parts[0]!
  const headline = `Company-hosted data center meetings listed ${where(place)} number ${atLeast}${fmt(items.length)}: ${named}.`
  return {
    headline,
    context: 'Listed in news and company announcements. That is the record. Where do you stand now?',
    empty: false,
    failed: false,
  }
}

/** The share of speakers one side needs before the overview says which way the place's speakers went (#1115). */
export const OVERVIEW_LEAN_SHARE = 2 / 3

/**
 * The overview headline for a place from its speaker counts (#1115), or null when fewer speakers are on record than the
 * national conclusion needs (`minSpeakers`). Counts are the scope's whole positions totals: speakers for, against, asking a
 * question and taking no side. A side with at least two thirds of them leads; otherwise the place was split. These are
 * counts of speakers at meetings, not a survey, and the sentence says only that.
 */
export function overviewLean(res: DataCenterPositionsResponse | null | undefined, place: string): string | null {
  const c = speakerCounts(res)
  const min = STORIES['data-centers']!.conclusion!.minSpeakers
  if (!c || c.total < min) return null
  // #1289: a lean opposite the recorded votes is not stated as a lean.
  const t = res?.available ? res.totals : null
  const tallies = t?.decisions_with_tally ?? 0
  const vf = t?.votes_for ?? 0
  const va = t?.votes_against ?? 0
  const votes = tallies > 0 && vf !== va ? (vf > va ? 'for' : 'against') : null
  const lean = c.against / c.total >= OVERVIEW_LEAN_SHARE ? 'against' : c.for / c.total >= OVERVIEW_LEAN_SHARE ? 'for' : null
  if (lean && votes && lean !== votes) {
    return `${place} was divided: ${fmt(c[lean])} of ${plural(c.total, 'speaker')} spoke ${lean} data centers, while recorded votes went ${fmt(vf)} for and ${fmt(va)} against.`
  }
  if (c.against / c.total >= OVERVIEW_LEAN_SHARE) {
    return `${place} pushed back: ${fmt(c.against)} of ${plural(c.total, 'speaker')} spoke against data centers.`
  }
  if (c.for / c.total >= OVERVIEW_LEAN_SHARE) {
    return `${place} welcomed data centers: ${fmt(c.for)} of ${plural(c.total, 'speaker')} spoke for them.`
  }
  // A split needs speakers on both sides; never "0 spoke for" (#1134).
  if (c.for <= 0 || c.against <= 0) return null
  return `${place} was split: ${fmt(c.for)} spoke for and ${fmt(c.against)} against data centers.`
}

const normTitle = (t: string) => t.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()

/**
 * A screen headline that is not the page's title (#1222): the first candidate that differs from `title` (ignoring case and
 * punctuation), or null. The story header states the title; the Overview (and a topic story's) leads with its own line.
 */
export function distinctHeadline(title: string | null | undefined, ...candidates: (string | null | undefined)[]): string | null {
  const t = title ? normTitle(title) : ''
  for (const c of candidates) if (c && normTitle(c) !== t) return c
  return null
}

function overviewText(data: StoryData, scope: StoryScope, caption?: ScreenCaption | null): ScreenText {
  const stats = storyStats(data)
  const place = scope.stateName ? storyScopeLabel(scope) : null
  const byKey = new Map(stats.map((s) => [s.key, s.value]))
  const context = 'First, where are they?'
  const meetings = byKey.get('meetings')
  const passages = byKey.get('passages')
  const agendas = byKey.get('agendas')
  // The opener's headline is always a claim from meeting records; sites and projects never lead it.
  // At a state or city scope with enough speakers on record, the headline says which way they spoke (#1115) and the meeting
  // count becomes the context line. Below the national conclusion's minimum the neutral count stays: nothing is overstated.
  // The title is said once (#1222, owner 2026-11-26): the header states the caption; the Overview never repeats it. With a
  // conclusion caption it leads with its own count of the record instead (and never a different, stronger speaker claim).
  if (caption && caption.kind !== 'question' && caption.text) {
    const lead = distinctHeadline(
      caption.text,
      meetings ? `A data center came up in ${plural(meetings, 'meeting')} ${where(place)}.` : null,
      passages ? `Meeting passages that mention a data center ${where(place)} number ${fmt(passages)}.` : null,
      agendas ? `Meeting agendas that name a data center ${where(place)} number ${fmt(agendas)}.` : null,
    )
    if (lead) return { headline: lead, context, empty: false, failed: false }
  }
  const lean = place ? overviewLean(data.positions as DataCenterPositionsResponse | null | undefined, place) : null
  if (lean) {
    return {
      headline: lean,
      context: meetings ? `A data center came up in ${plural(meetings, 'meeting')}. ${context}` : context,
      empty: false,
      failed: false,
    }
  }
  if (meetings) return { headline: `A data center came up in ${plural(meetings, 'meeting')} ${where(place)}.`, context, empty: false, failed: false }
  if (passages) return { headline: `Meeting passages that mention a data center ${where(place)} number ${fmt(passages)}.`, context, empty: false, failed: false }
  if (agendas) return { headline: `Meeting agendas that name a data center ${where(place)} number ${fmt(agendas)}.`, context, empty: false, failed: false }
  if (stats.length === 0) return noData(scope)
  return {
    headline: scope.stateName ? 'No meeting records are available for this place.' : 'No meeting records are available.',
    context: 'These counts come from other sources. Try a wider place for meeting records.',
    empty: Boolean(scope.stateName),
    failed: false,
  }
}

/** What "Pause for now" means, in one line under the answers. */
export const PAUSE_NOTE = 'A pause is a moratorium: no new approvals until the rules are settled.'

/** Headline and context for one screen. Loading and failed screens get a neutral description, never a number. */
/** The caption's kind and its plain sentence, for the Overview (#1134); from pickCaption + captionText. */
export interface ScreenCaption {
  kind: string
  text: string
}

export function screenText(
  screen: StoryScreen,
  data: StoryData,
  status: StoryStatus,
  scope: StoryScope,
  question?: Pick<StanceQuestion, 'text' | 'place_text'> | null,
  /** The page's caption (utils/storyCaption, #1125): the Overview states it when it is a conclusion (#1134). */
  caption?: ScreenCaption | null,
): ScreenText {
  // The three screens around the record carry the story's question, worded for the place in scope.
  if (screen.kind === 'question') {
    return { headline: question ? questionText(question, scope) : 'The question', context: PAUSE_NOTE, empty: false, failed: false }
  }
  if (screen.kind === 'scope') {
    return { headline: 'Where?', context: 'Pick a city, a county or a state. Or stay with the whole country.', empty: false, failed: false }
  }
  if (screen.kind === 'verdict') {
    return {
      headline: "You've seen the record. Where do you stand now?",
      context: question ? questionText(question, scope) : '',
      empty: false,
      failed: false,
    }
  }
  if (screen.kind === 'overview') {
    const keys = STORY_CHARTS
    if (keys.every((k) => (status[k] ?? 'loading') === 'loading')) {
      return { headline: 'Data centers in the public record', context: 'Loading the records…', empty: false, failed: false }
    }
    if (keys.every((k) => status[k] === 'error')) {
      return { headline: 'Data centers in the public record', context: 'The records could not be loaded right now.', empty: false, failed: true }
    }
    return overviewText(data, scope, caption)
  }
  const key = screen.chart!
  const st = status[key] ?? 'loading'
  const neutral = chartTitle(key)
  if (st === 'loading') return { headline: neutral, context: 'Loading…', empty: false, failed: false }
  // The table behind "Who spoke up" may not be in the database yet: that is a quiet line, not an error.
  if (key === 'positions' && (st === 'error' || !positionsLoaded(data[key] as DataCenterPositionsResponse | null | undefined))) {
    return { headline: 'Who spoke up about data centers', context: POSITIONS_NOT_LOADED, empty: false, failed: false }
  }
  // Same for the decisions table (#933): not loaded is not "no data here", and broadening can't help.
  if (key === 'decisions' && st === 'ready' && (data[key] as DataCenterDecisionsResponse | null | undefined)?.available === false) {
    return { headline: 'Decisions on data center items', context: DECISIONS_NOT_LOADED, empty: false, failed: false }
  }
  if (st === 'error') return { headline: neutral, context: 'This part of the data could not be loaded right now.', empty: false, failed: true }
  const d = data[key]
  if (!d) return noData(scope)
  let out: ScreenText | null = null
  switch (key) {
    case 'positions':
      return positionsText(d as DataCenterPositionsResponse, scope)
    case 'sites':
      out = sitesText(d as DataCenterSitesResponse, scope)
      break
    case 'projects':
      out = projectsText(d as DataCenterProjectsResponse, scope)
      break
    case 'job-claims':
      out = jobsText(d as JobClaimsResponse, scope)
      break
    case 'concerns':
      out = concernsText(d as AreaConcernsResponse, scope)
      break
    case 'meeting-mentions':
      out = meetingsText(d as DataCenterMeetingMentionsResponse, scope)
      break
    case 'agenda-items':
      out = agendasText(d as DataCenterAgendaItemsResponse, scope)
      break
    case 'decisions':
      out = decisionsText(d as DataCenterDecisionsResponse, scope)
      break
    case 'community-events':
      out = gatheringsText(d as CommunityEventsResponse, scope)
      break
  }
  return out ?? noData(scope)
}

/** The accessible name of a progress stop: the screen's headline when the data gives one, otherwise its eyebrow word. */
export function stopLabel(screen: StoryScreen, text: ScreenText): string {
  return text.empty || text.failed ? screen.eyebrow : text.headline
}

// --- links the story offers -------------------------------------------------------------------------------------------

/** "?state=AL&city=Tuscaloosa" (or an empty string): the scope carried to every link. */
export function scopeQuery(scope: Pick<StoryScope, 'stateCode' | 'city'>): string {
  const q = new URLSearchParams()
  if (scope.stateCode) q.set('state', scope.stateCode)
  if (scope.stateCode && scope.city) q.set('city', scope.city)
  const s = q.toString()
  return s ? `?${s}` : ''
}

