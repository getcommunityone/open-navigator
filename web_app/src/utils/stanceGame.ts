// Pure helpers for the Data Center Challenge (#852) and the data stories (#884). Nothing here invents a number: every figure comes
// from an API response, and missing or empty data gives null.
import type {
  AreaConcernsResponse,
  CommunityEventsResponse,
  DataCenterAgendaItemsResponse,
  DataCenterMeetingMentionsResponse,
  DataCenterProjectsResponse,
  DataCenterSitesResponse,
  JobClaimsResponse,
} from '../api/dataCenters'
import type { GroupResult, StanceAnswer } from '../api/stance'
import { communityEventKindLabel, concernLabel } from '../lib/dataCenterJobs'
import { largestRemainder } from './matrixMapMath'

export type ChartKey =
  | 'job-claims'
  | 'sites'
  | 'concerns'
  | 'meeting-mentions'
  | 'agenda-items'
  | 'community-events'
  | 'projects'

export type ChartData =
  | JobClaimsResponse
  | DataCenterSitesResponse
  | AreaConcernsResponse
  | DataCenterMeetingMentionsResponse
  | DataCenterAgendaItemsResponse
  | CommunityEventsResponse
  | DataCenterProjectsResponse

export const ANSWER_LABEL: Record<StanceAnswer, string> = { agree: 'Agree', disagree: 'Disagree', unsure: 'Not sure' }
const ANSWER_ORDER: StanceAnswer[] = ['agree', 'disagree', 'unsure']

export interface ResultBar {
  answer: StanceAnswer
  label: string
  count: number
  /** Whole percent; the three always sum to 100 (largest remainder). */
  percent: number
}

function countsOf(group: GroupResult | null | undefined): Record<StanceAnswer, number> | null {
  if (!group || !group.available) return null
  const { agree, disagree, unsure } = group
  if (agree == null || disagree == null || unsure == null) return null
  return { agree, disagree, unsure }
}

/** The three bars for a group, or null when the group is unavailable (never a split below the minimum sample). */
export function resultBars(group: GroupResult | null | undefined): ResultBar[] | null {
  const c = countsOf(group)
  if (!c) return null
  const values = ANSWER_ORDER.map((a) => c[a])
  const pct = largestRemainder(values, 100)
  if (pct.length === 0) return null
  return ANSWER_ORDER.map((a, i) => ({ answer: a, label: ANSWER_LABEL[a], count: c[a], percent: pct[i]! }))
}

/**
 * Was the player's answer the larger group, a smaller one, or tied? "Tie" when the top two counts are equal.
 * "Not sure" answers and unavailable groups give null.
 */
export function sidedWith(
  answer: StanceAnswer | null | undefined,
  group: GroupResult | null | undefined,
): 'majority' | 'minority' | 'tie' | null {
  if (!answer || answer === 'unsure') return null
  const c = countsOf(group)
  if (!c) return null
  const sorted = ANSWER_ORDER.map((a) => c[a]).sort((a, b) => b - a)
  if (sorted[0] === sorted[1]) return 'tie'
  return c[answer] === sorted[0] ? 'majority' : 'minority'
}

const WORDS = [
  'zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
  'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen', 'twenty',
]

/** "one" ... "twenty", then the numeral. */
export function roundWord(n: number): string {
  if (!Number.isInteger(n) || n < 1) return String(n)
  return n <= 20 ? WORDS[n]! : String(n)
}

// --- findings: one sentence per chart, from that endpoint's real data ---------------------------------------------

export const fmt = (n: number) => n.toLocaleString('en-US')
/** "in Alabama" or "nationally". */
export const where = (place: string | null | undefined) => (place ? `in ${place}` : 'nationally')
export const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

export function tally<T>(items: T[], keyOf: (x: T) => string | null): Array<{ key: string; count: number }> {
  const m = new Map<string, number>()
  for (const it of items) {
    const k = keyOf(it)
    if (k == null) continue
    m.set(k, (m.get(k) ?? 0) + 1)
  }
  return [...m.entries()].map(([key, count]) => ({ key, count })).sort((a, b) => b.count - a.count || a.key.localeCompare(b.key))
}

export function findingJobClaims(res: JobClaimsResponse | null | undefined, place?: string | null): string | null {
  const c = res?.totals?.construction ?? 0
  const o = res?.totals?.operations ?? 0
  if (c + o <= 0) return null
  return `Meetings ${where(place)} include ${fmt(c)} jobs claims for construction and ${fmt(o)} for operations.`
}

export function findingSites(res: DataCenterSitesResponse | null | undefined, place?: string | null): string | null {
  const k = res?.counts
  if (!k) return null
  const total = k.planned + k.under_construction + k.operating + k.no_longer_listed + k.status_not_published
  if (total <= 0) return null
  return `Of ${fmt(total)} data center ${total === 1 ? 'site' : 'sites'} on record ${where(place)}, ${fmt(k.operating)} ${k.operating === 1 ? 'is' : 'are'} operating, ${fmt(k.under_construction)} under construction and ${fmt(k.planned)} planned.`
}

/** The concern list that matches the scope: the area's own when a state is chosen, otherwise the national one. */
export function concernList(res: AreaConcernsResponse, place?: string | null) {
  return place ? res.items : res.national
}

export function findingConcerns(res: AreaConcernsResponse | null | undefined, place?: string | null): string | null {
  if (!res) return null
  const list = concernList(res, place) ?? []
  const total = list.reduce((a, c) => a + c.mention_count, 0)
  if (list.length === 0 || total <= 0) return null
  const sorted = [...list].sort((a, b) => b.mention_count - a.mention_count || a.concern.localeCompare(b.concern))
  const top = sorted[0]!
  const second = sorted[1]
  if (second && second.mention_count === top.mention_count) {
    return `${cap(concernLabel(top.concern))} and ${concernLabel(second.concern)} tied as the most raised concerns in meetings ${where(place)}: ${fmt(top.mention_count)} mentions each of ${fmt(total)}.`
  }
  return `${cap(concernLabel(top.concern))} was the #1 concern in meetings ${where(place)}: ${fmt(top.mention_count)} of ${fmt(total)} mentions.`
}

export function yearOf(date: string | null | undefined): string | null {
  const y = typeof date === 'string' ? date.slice(0, 4) : ''
  return /^\d{4}$/.test(y) ? y : null
}

export function findingMeetingMentions(
  res: DataCenterMeetingMentionsResponse | null | undefined,
  place?: string | null,
): string | null {
  const items = res?.items ?? []
  const years = tally(items, (m) => yearOf(m.meeting_date))
  if (years.length === 0) return null
  const top = years[0]!
  const dated = years.reduce((a, y) => a + y.count, 0)
  const total = res?.counts?.passages ?? 0
  const tail = total > items.length ? ` (${fmt(total)} passages on record ${where(place)})` : ''
  return `The year ${top.key} has the most meeting passages about data centers ${where(place)}: ${fmt(top.count)} of the ${fmt(dated)} most recent${tail}.`
}

export function findingAgendaItems(res: DataCenterAgendaItemsResponse | null | undefined, place?: string | null): string | null {
  const u = res?.counts?.upcoming ?? 0
  const p = res?.counts?.past ?? 0
  if (u + p <= 0) return null
  return `Of ${fmt(u + p)} meeting ${u + p === 1 ? 'agenda that mentions' : 'agendas that mention'} a data center ${where(place)}, ${fmt(u)} ${u === 1 ? 'is' : 'are'} upcoming and ${fmt(p)} past.`
}

export function findingCommunityEvents(res: CommunityEventsResponse | null | undefined, place?: string | null): string | null {
  const items = res?.items ?? []
  if (items.length === 0) return null
  const top = tally(items, (e) => e.event_kind)[0]!
  return `${cap(communityEventKindLabel(top.key).toLowerCase())} is the most common company-hosted meeting ${where(place)}: ${fmt(top.count)} of ${fmt(items.length)} events.`
}

export function statusLabel(status: string | null | undefined): string {
  if (!status) return 'Status not published'
  const s = status.replace(/_/g, ' ')
  return cap(s)
}

export function findingProjects(res: DataCenterProjectsResponse | null | undefined, place?: string | null): string | null {
  const items = res?.items ?? []
  if (items.length === 0) return null
  const top = tally(items, (p) => statusLabel(p.status))[0]!
  const total = Math.max(res?.total ?? 0, items.length)
  return `Most data center projects ${where(place)} are listed as "${top.key}": ${fmt(top.count)} of ${fmt(items.length)}${total > items.length ? ` shown (${fmt(total)} on record)` : ''}.`
}

/** The one-sentence finding for a chart key, or null when the data is empty or missing. */
export function findingFor(key: string, data: ChartData | null | undefined, place?: string | null): string | null {
  if (!data) return null
  switch (key as ChartKey) {
    case 'job-claims':
      return findingJobClaims(data as JobClaimsResponse, place)
    case 'sites':
      return findingSites(data as DataCenterSitesResponse, place)
    case 'concerns':
      return findingConcerns(data as AreaConcernsResponse, place)
    case 'meeting-mentions':
      return findingMeetingMentions(data as DataCenterMeetingMentionsResponse, place)
    case 'agenda-items':
      return findingAgendaItems(data as DataCenterAgendaItemsResponse, place)
    case 'community-events':
      return findingCommunityEvents(data as CommunityEventsResponse, place)
    case 'projects':
      return findingProjects(data as DataCenterProjectsResponse, place)
    default:
      return null
  }
}

// --- the chart for each key ---------------------------------------------------------------------------------------

export interface ChartRow {
  label: string
  value: number
  /** Whole-number share of all rows (largest remainder, so shares sum to 100). */
  percent: number
}

export interface Dot {
  id: string
  title: string
  place: string | null
  date: string | null
  /** The source record to open (meeting video, agenda document, article, site source). Null when the record has none. */
  url: string | null
}

export interface DotGroup {
  key: string
  label: string
  /** Dots drawn for this group. */
  shown: number
  /** Real whole-scope count for this group when the endpoint returns one for this grouping, otherwise null. */
  total: number | null
  /** Real share of the whole-scope total (whole percent), or null when the total is unknown. Never computed from drawn dots. */
  share: number | null
  /** The heading text, from `dotGroupHeading`. */
  heading: string
  dots: Dot[]
}

interface ChartBase {
  /** What the figure counts, for the FIG. caption and the table header. */
  title: string
  /** Where the numbers come from. */
  source: string
  /** Extra honesty about what was counted (for example "Showing the most recent 500 of 1,204."). Null when complete. */
  note: string | null
}
export interface BarsSpec extends ChartBase {
  kind: 'bars'
  rows: ChartRow[]
}
export interface DotsSpec extends ChartBase {
  kind: 'dots'
  /** "agenda item": one dot is one of these. */
  unit: string
  groups: DotGroup[]
  /** How many dots are drawn. */
  drawn: number
  /** Real whole-scope total across all groups, or null when the endpoint returns no count for this grouping. */
  grandTotal: number | null
}
export type ChartSpec = BarsSpec | DotsSpec

/** Most dots drawn in one chart. The data-center endpoints are asked for at most this many records. */
export const DOT_CAP = 500

/** What each chart is, in neutral words: the headline when the data cannot support a sentence. */
export const CHART_TITLES: Record<ChartKey, string> = {
  'job-claims': 'Jobs claims made in public meetings, by phase',
  sites: 'Data center sites on record, by status',
  concerns: 'What people raise about data centers in their meetings',
  'meeting-mentions': 'Meeting passages that mention a data center, by year',
  'agenda-items': 'Meeting agendas that mention a data center',
  'community-events': 'Company-hosted data center meetings, by kind',
  projects: 'Data center projects, by status',
}

export function chartTitle(key: string): string {
  return CHART_TITLES[key as ChartKey] ?? 'Chart'
}

function barRows(rows: Array<{ label: string; value: number }>): ChartRow[] {
  const pct = largestRemainder(
    rows.map((r) => r.value),
    100,
  )
  return rows.map((r, i) => ({ ...r, percent: pct[i] ?? 0 }))
}

/** Whole percent of `total` in `grandTotal`; null unless both are real counts. */
export function groupShare(total: number | null, grandTotal: number | null): number | null {
  if (total == null || grandTotal == null || grandTotal <= 0) return null
  return Math.round((100 * total) / grandTotal)
}

/**
 * A dot group's heading. With a real whole-scope count it states that count and its real share, and says how many dots
 * are drawn when that is fewer ("Operating · 118 records · 60% · showing 24"). Without one it states only what is drawn
 * ("Operating · 24 shown") and never a share or a total: a share is never computed from a capped list.
 */
export function dotGroupHeading(g: { label: string; shown: number; total: number | null; grandTotal: number | null }): string {
  if (g.total == null) return `${g.label} · ${fmt(g.shown)} shown`
  const pct = groupShare(g.total, g.grandTotal)
  const head = `${g.label} · ${fmt(g.total)} ${g.total === 1 ? 'record' : 'records'}${pct == null ? '' : ` · ${pct}%`}`
  return g.shown < g.total ? `${head} · showing ${fmt(g.shown)}` : head
}

function dotGroups(
  groups: Array<{ key: string; label: string; dots: Dot[]; total?: number | null }>,
): { groups: DotGroup[]; grandTotal: number | null } {
  const live = groups.filter((g) => g.dots.length > 0 || (g.total ?? 0) > 0)
  const allKnown = live.length > 0 && live.every((g) => g.total != null)
  const grandTotal = allKnown ? live.reduce((a, g) => a + (g.total ?? 0), 0) : null
  return {
    grandTotal,
    groups: live.map((g) => {
      const total = g.total ?? null
      const shown = g.dots.length
      return {
        key: g.key,
        label: g.label,
        dots: g.dots,
        shown,
        total,
        share: groupShare(total, grandTotal),
        heading: dotGroupHeading({ label: g.label, shown, total, grandTotal }),
      }
    }),
  }
}

const joinPlace = (name?: string | null, state?: string | null) => [name, state].filter(Boolean).join(', ') || null

function capNote(drawn: number, onRecord: number | null): string | null {
  if (onRecord != null && onRecord > drawn) return `Showing the most recent ${fmt(drawn)} of ${fmt(onRecord)}.`
  if (onRecord == null && drawn >= DOT_CAP) return `Showing the first ${fmt(DOT_CAP)} returned; there may be more.`
  return null
}

/** Rows or dots for the key's chart, or null when there is nothing to draw (the round shows "No data available for this chart"). */
export function chartSpec(key: string, data: ChartData | null | undefined, place?: string | null): ChartSpec | null {
  if (!data) return null
  const bars = (title: string, source: string, rows: Array<{ label: string; value: number }>, note: string | null = null): BarsSpec | null =>
    rows.some((r) => r.value > 0) ? { kind: 'bars', title, source, note, rows: barRows(rows) } : null
  const dots = (
    title: string,
    source: string,
    unit: string,
    groups: Array<{ key: string; label: string; dots: Dot[]; total?: number | null }>,
    onRecord: number | null,
  ): DotsSpec | null => {
    const { groups: g, grandTotal } = dotGroups(groups)
    const drawn = g.reduce((a, x) => a + x.shown, 0)
    return drawn > 0 ? { kind: 'dots', title, source, note: capNote(drawn, onRecord), unit, groups: g, drawn, grandTotal } : null
  }
  switch (key as ChartKey) {
    case 'job-claims': {
      const t = (data as JobClaimsResponse).totals
      return bars(CHART_TITLES['job-claims'], 'Open Navigator, claims quoted from meeting transcripts', [
        { label: 'Construction', value: t?.construction ?? 0 },
        { label: 'Operations', value: t?.operations ?? 0 },
      ])
    }
    case 'sites': {
      const res = data as DataCenterSitesResponse
      const k = res.counts
      const on = k ? k.planned + k.under_construction + k.operating + k.no_longer_listed + k.status_not_published : null
      const order = ['operating', 'under_construction', 'planned', 'no_longer_listed', '']
      const names: Record<string, string> = {
        operating: 'Operating',
        under_construction: 'Under construction',
        planned: 'Planned',
        no_longer_listed: 'No longer listed',
        '': 'Status not published',
      }
      const items = res.items ?? []
      return dots(
        CHART_TITLES.sites,
        'Epoch AI data center sites, CC BY 4.0',
        'data center site',
        order.map((st) => ({
          key: st || 'none',
          label: names[st]!,
          total: k ? (st === '' ? k.status_not_published : k[st as 'operating' | 'planned' | 'under_construction' | 'no_longer_listed']) : null,
          dots: items
            .filter((i) => (i.status ?? '') === st)
            .map((i) => ({
              id: i.data_center_site_id,
              title: i.site_name,
              place: i.state ?? i.state_code ?? null,
              date: i.status_as_of ?? null,
              url: i.source_url || null,
            })),
        })),
        on,
      )
    }
    case 'concerns': {
      const list = concernList(data as AreaConcernsResponse, place) ?? []
      return bars(
        CHART_TITLES.concerns,
        'Open Navigator, concerns found in meeting transcripts',
        [...list]
          .sort((a, b) => b.mention_count - a.mention_count || a.concern.localeCompare(b.concern))
          .map((c) => ({ label: cap(concernLabel(c.concern)), value: c.mention_count })),
      )
    }
    case 'meeting-mentions': {
      const res = data as DataCenterMeetingMentionsResponse
      const items = res.items ?? []
      const years = [...new Set(items.map((m) => yearOf(m.meeting_date) ?? ''))].sort((a, b) =>
        a === '' ? 1 : b === '' ? -1 : b.localeCompare(a),
      )
      return dots(
        CHART_TITLES['meeting-mentions'],
        'Open Navigator, passages quoted from meeting transcripts',
        'meeting passage',
        years.map((y) => ({
          key: y || 'none',
          label: y || 'Date not given',
          dots: items
            .filter((m) => (yearOf(m.meeting_date) ?? '') === y)
            .map((m) => ({
              id: m.data_center_meeting_mention_id,
              title: m.meeting_title ?? 'Meeting passage',
              place: joinPlace(m.jurisdiction_name, m.state_code),
              date: m.meeting_date ?? null,
              url: m.jump_url ?? m.video_url ?? null,
            })),
        })),
        res.counts?.passages ?? null,
      )
    }
    case 'agenda-items': {
      const res = data as DataCenterAgendaItemsResponse
      const items = res.items ?? []
      const on = res.counts ? res.counts.upcoming + res.counts.past : null
      const toDot = (a: (typeof items)[number]): Dot => ({
        id: a.data_center_agenda_item_id,
        title: a.meeting_title ?? a.body_name ?? 'Meeting agenda',
        place: joinPlace(a.jurisdiction_name, a.state_code),
        date: a.doc_date ?? null,
        url: a.document_url ?? null,
      })
      return dots(
        CHART_TITLES['agenda-items'],
        'Open Navigator, agendas of local government meetings',
        'agenda item',
        [
          { key: 'upcoming', label: 'Upcoming meetings', total: res.counts?.upcoming ?? null, dots: items.filter((a) => a.is_upcoming).map(toDot) },
          { key: 'past', label: 'Past meetings', total: res.counts?.past ?? null, dots: items.filter((a) => !a.is_upcoming).map(toDot) },
        ],
        on,
      )
    }
    case 'community-events': {
      const items = (data as CommunityEventsResponse).items ?? []
      const kinds = [...new Set(items.map((e) => e.event_kind))]
      return dots(
        CHART_TITLES['community-events'],
        'Open Navigator, from news and company announcements',
        'company-hosted meeting',
        kinds.map((k) => ({
          key: k,
          label: communityEventKindLabel(k),
          dots: items
            .filter((e) => e.event_kind === k)
            .map((e) => ({
              id: e.community_event_id,
              title: e.title,
              place: joinPlace(e.city, e.state_code),
              date: e.event_date ?? e.first_reported_on ?? null,
              url: e.recording_url ?? e.sources?.[0]?.url ?? null,
            })),
        })),
        null,
      )
    }
    case 'projects': {
      const res = data as DataCenterProjectsResponse
      const items = res.items ?? []
      const total = Math.max(res.total ?? 0, items.length)
      return bars(
        CHART_TITLES.projects,
        'Open Navigator, curated announcements and Epoch AI',
        tally(items, (p) => statusLabel(p.status)).map((t) => ({ label: t.key, value: t.count })),
        total > items.length ? `Counted from ${fmt(items.length)} of ${fmt(total)} projects.` : null,
      )
    }
    default:
      return null
  }
}

/** The headline for a round: the finding sentence, or a neutral description of the chart when the data cannot support one. */
export function roundHeadline(key: string, finding: string | null): { text: string; isFinding: boolean } {
  return finding ? { text: finding, isFinding: true } : { text: chartTitle(key), isFinding: false }
}

// --- end screen ---------------------------------------------------------------------------------------------------

export interface Tally {
  /** Rounds with an available group and a Agree/Disagree answer that were not a tie. */
  compared: number
  withLarger: number
}

/** Rounds where the player was with the larger group; only rounds with an available group count. */
export function tallySided(
  rounds: Array<{ answer: StanceAnswer | null | undefined; group: GroupResult | null | undefined }>,
): Tally {
  let compared = 0
  let withLarger = 0
  for (const r of rounds) {
    const s = sidedWith(r.answer, r.group)
    if (s === 'majority') {
      compared += 1
      withLarger += 1
    } else if (s === 'minority') compared += 1
  }
  return { compared, withLarger }
}

/** The "Your place" label: always states exactly what the results are filtered to. */
export function placeLabel(stateName: string | null, city: string | null): string {
  if (!stateName) return 'National only'
  return city ? `${city}, ${stateName}` : stateName
}

// --- The beats of a round (#899) ------------------------------------------------------------------------------------------

/** The three beats of a round: the finding and chart, then the question, then the results. */
export type RoundBeat = 'finding' | 'question' | 'results'

/**
 * Which beat a round is in. An answer the player may still change goes back to the question; a confirmed answer shows the
 * results (also when the player returns to the round); otherwise the question shows once it has been asked, else the finding.
 */
export function roundBeat(state: { answered: boolean; asked: boolean; changing?: boolean }): RoundBeat {
  if (state.changing) return 'question'
  if (state.answered) return 'results'
  return state.asked ? 'question' : 'finding'
}

/** Milliseconds the chart waits before it starts to draw, and how long the draw takes (the CSS animation uses the same). */
export const CHART_DRAW_DELAY_MS = 350
export const CHART_DRAW_MS = 1100
/** The pause after the chart has finished drawing before the question arrives on its own. */
export const ASK_PAUSE_MS = 2500
/** How long the chosen answer shows locked before the results start to land, and the gap between result rows. */
export const LOCK_HOLD_MS = 450
export const BAR_GAP_MS = 650
export const BAR_FIRST_MS = 150

/** Milliseconds of "chart ready" time before the question arrives by itself (no drawing with reduced motion). */
export function askAfterMs(reducedMotion: boolean): number {
  return reducedMotion ? ASK_PAUSE_MS : CHART_DRAW_DELAY_MS + CHART_DRAW_MS + ASK_PAUSE_MS
}
