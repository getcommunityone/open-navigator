// Pure copy and structure for the data stories (#884). Every sentence is computed from an API response: a figure is stated
// only when the endpoint returned it for the whole scope (never from a capped list), missing data gives a neutral
// description, and nothing here invents a number. Voice: contrasts, counts, rankings, shares and change over time. No causes,
// forecasts, judgments or claims about what people in general think: the records are meeting records, not a survey.
import type {
  AreaConcernsResponse,
  CommunityEventsResponse,
  DataCenterAgendaItemsResponse,
  DataCenterMeetingMentionsResponse,
  DataCenterProjectsResponse,
  DataCenterSitesResponse,
  JobClaimsResponse,
} from '../api/dataCenters'
import { communityEventKindLabel, concernLabel } from '../lib/dataCenterJobs'
import type { StanceQuestion } from '../api/stance'
import { questionText } from './storyQuestion'
import {
  DOT_CAP,
  cap,
  chartTitle,
  concernList,
  fmt,
  statusLabel,
  tally,
  where,
  yearOf,
  type ChartData,
  type ChartKey,
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
   * `question` asks the story's question before the record, `scope` sets the place, `verdict` asks it again at the end and
   * shows how readers answered (#915). `overview` is the row of counts and `chart` one dataset.
   */
  kind: 'question' | 'scope' | 'overview' | 'chart' | 'verdict'
  /** "For context": the screen is records about the topic that are not something said in a meeting (sites, projects). */
  kicker?: string
}

/** The Data Center Story, in order: the question, the place, the record, then the question again. */
export const DATA_CENTER_STORY: StoryScreen[] = [
  { id: 'question', eyebrow: 'The question', chart: null, kind: 'question' },
  { id: 'scope', eyebrow: 'Where', chart: null, kind: 'scope' },
  { id: 'overview', eyebrow: 'Overview', chart: null, kind: 'overview' },
  { id: 'sites', eyebrow: 'Sites', chart: 'sites', kind: 'chart', kicker: 'For context' },
  { id: 'projects', eyebrow: 'Proposals', chart: 'projects', kind: 'chart', kicker: 'For context' },
  { id: 'jobs', eyebrow: 'Promises', chart: 'job-claims', kind: 'chart' },
  { id: 'concerns', eyebrow: 'Concerns', chart: 'concerns', kind: 'chart' },
  { id: 'meetings', eyebrow: 'Meetings', chart: 'meeting-mentions', kind: 'chart' },
  { id: 'agendas', eyebrow: 'Agendas', chart: 'agenda-items', kind: 'chart' },
  { id: 'gatherings', eyebrow: 'Gatherings', chart: 'community-events', kind: 'chart' },
  { id: 'verdict', eyebrow: 'Your answer', chart: null, kind: 'verdict' },
]

/** Screen ids that were renamed: an old link still lands on the screen that replaced it. */
const SCREEN_ALIASES: Record<string, string> = { turn: 'verdict' }

/** The position of the screen a `?screen=` value names, or -1. */
export function storyScreenIndex(screens: StoryScreen[], param: string | null | undefined): number {
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
  if (key === 'sites') return 'Epoch AI data center sites'
  if (key === 'projects') return 'curated announcements and Epoch AI'
  return null
}

/** The place as it reads in "What did ___ say about ...?": "the United States", "Alabama" or "Tuscaloosa, Alabama". */
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
  const siteTotal = k ? k.planned + k.under_construction + k.operating + k.no_longer_listed + k.status_not_published : 0
  // Counts from meeting recordings and transcripts lead; counts from other sources follow with their source named.
  const all: StoryStat[] = [
    { key: 'meetings', value: mentions?.counts?.meetings ?? 0, label: 'meetings where a data center came up' },
    { key: 'passages', value: mentions?.counts?.passages ?? 0, label: 'meeting passages quoted' },
    { key: 'agendas', value: agendas?.counts ? agendas.counts.upcoming + agendas.counts.past : 0, label: 'meeting agendas that name one' },
    { key: 'claims', value: (claims?.totals?.construction ?? 0) + (claims?.totals?.operations ?? 0), label: 'jobs claims made in meetings' },
    { key: 'sites', value: siteTotal, label: `data center sites on record${scope.city && scope.stateName ? ` in ${scope.stateName}` : ''}, from Epoch AI` },
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

function sitesText(res: DataCenterSitesResponse, scope: StoryScope): ScreenText | null {
  const k = res.counts
  if (!k) return null
  const total = k.planned + k.under_construction + k.operating + k.no_longer_listed + k.status_not_published
  if (total <= 0) return null
  const place = placeFor('sites', scope)
  const pipeline = k.planned + k.under_construction
  const headline =
    k.operating === 0
      ? `None of the ${plural(total, 'data center site')} ${where(place)} ${total === 1 ? 'is' : 'are'} listed as operating; ${fmt(pipeline)} ${pipeline === 1 ? 'is' : 'are'} planned or under construction.`
      : `Of ${plural(total, 'data center site')} ${where(place)}, ${fmt(k.operating)} ${k.operating === 1 ? 'is' : 'are'} operating, and ${fmt(pipeline)} more ${pipeline === 1 ? 'is' : 'are'} planned or under construction.`
  const rest: string[] = []
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
    context: `${complete ? '' : `The bars count the ${fmt(items.length)} listed. `}What gets promised in meetings?`,
    empty: false,
    failed: false,
  }
}

function jobsText(res: JobClaimsResponse, scope: StoryScope): ScreenText | null {
  const c = res.totals?.construction ?? 0
  const o = res.totals?.operations ?? 0
  if (c + o <= 0) return null
  const place = placeFor('job-claims', scope)
  let headline: string
  if (c > 0 && o > 0) {
    headline = `Meetings ${where(place)} include ${plural(c, 'claim')} about construction jobs and ${plural(o, 'claim')} about operations jobs.`
  } else if (c > 0) {
    headline = `Meetings ${where(place)} include ${plural(c, 'claim')} about construction jobs and none about operations jobs.`
  } else {
    headline = `Meetings ${where(place)} include ${plural(o, 'claim')} about operations jobs and none about construction jobs.`
  }
  const gap = Math.abs(c - o)
  const lead = c > 0 && o > 0 && gap > 0 ? `${c > o ? 'Construction' : 'Operations'} claims outnumber ${c > o ? 'operations' : 'construction'} claims by ${fmt(gap)}. ` : ''
  return {
    headline,
    context: `${lead}Each one was said in a public meeting. What concerns come up?`,
    empty: false,
    failed: false,
  }
}

function concernsText(res: AreaConcernsResponse, scope: StoryScope): ScreenText | null {
  const place = placeFor('concerns', scope)
  const list = concernList(res, place) ?? []
  const total = list.reduce((a, c) => a + c.mention_count, 0)
  if (list.length === 0 || total <= 0) return null
  const sorted = [...list].sort((a, b) => b.mention_count - a.mention_count || a.concern.localeCompare(b.concern))
  const top = sorted[0]!
  const second = sorted[1]
  const pct = Math.round((100 * top.mention_count) / total)
  const name = concernLabel(top.concern)
  let headline: string
  if (!second || second.mention_count <= 0) {
    headline = `${cap(name)} is the only concern found in meeting records ${where(place)}: ${plural(top.mention_count, 'mention')}.`
  } else if (second.mention_count === top.mention_count) {
    headline = `${cap(name)} and ${concernLabel(second.concern)} are tied as the most raised concerns in meeting records ${where(place)}: ${plural(top.mention_count, 'mention')} each, of ${fmt(total)}.`
  } else {
    headline = `${cap(name)} is raised most in meeting records ${where(place)}: ${fmt(top.mention_count)} of ${plural(total, 'mention')} (${pct}%), ahead of ${concernLabel(second.concern)} with ${fmt(second.mention_count)}.`
  }
  return {
    headline,
    context: 'These count passages in meeting transcripts, not people. When does it come up?',
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
  const headline =
    meetings > 0 && passages > 0
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
    context: 'Upcoming means the meeting date has not passed. What about meetings the companies host?',
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

function overviewText(data: StoryData, scope: StoryScope): ScreenText {
  const stats = storyStats(data)
  const place = scope.stateName ? storyScopeLabel(scope) : null
  const byKey = new Map(stats.map((s) => [s.key, s.value]))
  const context = 'First, where are they?'
  const meetings = byKey.get('meetings')
  const passages = byKey.get('passages')
  const agendas = byKey.get('agendas')
  // The opener's headline is always a claim from meeting records; sites and projects never lead it.
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
export function screenText(
  screen: StoryScreen,
  data: StoryData,
  status: StoryStatus,
  scope: StoryScope,
  question?: Pick<StanceQuestion, 'text' | 'place_text'> | null,
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
    return overviewText(data, scope)
  }
  const key = screen.chart!
  const st = status[key] ?? 'loading'
  const neutral = chartTitle(key)
  if (st === 'loading') return { headline: neutral, context: 'Loading…', empty: false, failed: false }
  if (st === 'error') return { headline: neutral, context: 'This part of the data could not be loaded right now.', empty: false, failed: true }
  const d = data[key]
  if (!d) return noData(scope)
  let out: ScreenText | null = null
  switch (key) {
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

export const challengePath = (packId: string, scope: Pick<StoryScope, 'stateCode' | 'city'>) =>
  `/challenge/${encodeURIComponent(packId)}${scopeQuery(scope)}`
