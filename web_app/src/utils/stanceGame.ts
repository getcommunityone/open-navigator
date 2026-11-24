// Pure helpers for the Data Center Challenge (#852) and the data stories (#884). Nothing here invents a number: every figure comes
// from an API response, and missing or empty data gives null.
import type {
  AreaConcernsResponse,
  CommunityEventsResponse,
  DataCenterAgendaItemsResponse,
  DataCenterMeetingMentionsResponse,
  DataCenterProjectsResponse,
  DataCenterSitesResponse,
  DataCenterPositionsResponse,
  JobClaimsResponse,
} from '../api/dataCenters'
import type { GroupResult, StanceAnswer } from '../api/stance'
import { communityEventKindLabel, concernLabel } from '../lib/dataCenterJobs'
import { largestRemainder } from './matrixMapMath'

export type ChartKey =
  | 'positions'
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
  | DataCenterPositionsResponse

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

export interface Dot {
  id: string
  title: string
  place: string | null
  date: string | null
  /** The source record to open (meeting video, agenda document, article, site source). Null when the record has none. */
  url: string | null
  /** How many records the dot stands for. Absent means one. Only a chart drawn from a count (no listed records) sets it. */
  weight?: number
}

/** A stance a dot group stands for: it picks the group's colour and its shape, so colour is never the only signal. */
export type DotTone = 'for' | 'against' | 'question' | 'neutral'

export interface DotGroup {
  key: string
  label: string
  tone?: DotTone
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
export interface DotsSpec extends ChartBase {
  kind: 'dots'
  /** "agenda item": one dot is one of these. */
  unit: string
  groups: DotGroup[]
  /** How many dots are drawn. */
  drawn: number
  /** Real whole-scope total across all groups, or null when the endpoint returns no count for this grouping. */
  grandTotal: number | null
  /** How many records one dot stands for: 1 unless the chart is drawn from a count too large to draw one for one. */
  perDot: number
  /** What a dot is, in words, from `dotMeaning`. */
  dotMeans: string
}
/** Every chart is a dot chart: one dot is one real record, or a stated number of them. */
export type ChartSpec = DotsSpec

/** Most dots drawn in one chart. The data-center endpoints are asked for at most this many records. */
export const DOT_CAP = 500
/** Most dots drawn for a chart that has only counts behind it (no listed records). Beyond it, one dot stands for several. */
export const COUNT_DOT_CAP = 240

/**
 * How many records one dot stands for so that `total` records fit in `cap` dots: 1, 2, 5, 10, 20, 50, 100... (the smallest
 * that fits). Always a whole number, so "each dot is 10 meetings" is exact.
 */
export function dotRatio(total: number, cap = COUNT_DOT_CAP): number {
  if (!(total > cap)) return 1
  for (let pow = 1; ; pow *= 10) {
    for (const m of [1, 2, 5]) {
      if (m * pow > 1 && Math.ceil(total / (m * pow)) <= cap) return m * pow
    }
  }
}

/**
 * Dots for a real count with no listed records: `count` records at `perDot` each. Every dot but the last stands for exactly
 * `perDot`; the last stands for what is left over, so the weights always add up to `count`. Zero gives no dots.
 */
export function countDots(key: string, count: number, perDot: number, unit: [string, string]): Dot[] {
  if (!Number.isFinite(count) || count <= 0) return []
  const full = Math.floor(count / perDot)
  const rest = count - full * perDot
  const weights = [...Array.from({ length: full }, () => perDot), ...(rest > 0 ? [rest] : [])]
  return weights.map((w, i) => ({
    id: `${key}-${i}`,
    title: `${fmt(w)} ${w === 1 ? unit[0] : unit[1]}`,
    place: null,
    date: null,
    url: null,
    ...(perDot > 1 ? { weight: w } : {}),
  }))
}

/** "Every dot is one speaker." or, for a count drawn at a ratio, "Each dot is 10 meetings; the last dot of a group is what is left over." */
export function dotMeaning(perDot: number, unit: [string, string]): string {
  if (perDot <= 1) return `Every dot is one ${unit[0]}.`
  return `Each dot is ${fmt(perDot)} ${unit[1]}; the last dot of a group is what is left over.`
}

/** What each chart is, in neutral words: the headline when the data cannot support a sentence. */
export const CHART_TITLES: Record<ChartKey, string> = {
  positions: 'People who spoke on a data center item at local meetings',
  'job-claims': 'Jobs claims made in local meetings, by phase',
  sites: 'Data center sites on record, by status',
  concerns: 'What people raise about data centers in their meetings',
  'meeting-mentions': 'Meeting passages that mention a data center, by year',
  'agenda-items': 'Meeting agendas that mention a data center',
  'community-events': 'Company-hosted data center meetings, by kind',
  projects: 'Data center projects, by status',
}

/** The overview's figure: the meetings count, drawn as dots. */
export const MEETINGS_TITLE = 'Local meetings where a data center came up'

export function chartTitle(key: string): string {
  return CHART_TITLES[key as ChartKey] ?? 'Chart'
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
export function dotGroupHeading(g: {
  label: string
  shown: number
  total: number | null
  grandTotal: number | null
  /** What is counted, singular and plural ("speaker", "speakers"); "record(s)" when not given. */
  unit?: [string, string]
}): string {
  if (g.total == null) return `${g.label} · ${fmt(g.shown)} shown`
  const pct = groupShare(g.total, g.grandTotal)
  const [one, many] = g.unit ?? ['record', 'records']
  const head = `${g.label} · ${fmt(g.total)} ${g.total === 1 ? one : many}${pct == null ? '' : ` · ${pct}%`}`
  return g.shown < g.total ? `${head} · showing ${fmt(g.shown)}` : head
}

type GroupIn = { key: string; label: string; dots: Dot[]; total?: number | null; tone?: DotTone }

function dotGroups(groups: GroupIn[], unit?: [string, string], ratio = false): { groups: DotGroup[]; grandTotal: number | null } {
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
        ...(g.tone ? { tone: g.tone } : {}),
        dots: g.dots,
        shown,
        total,
        share: groupShare(total, grandTotal),
        // Dots drawn at a ratio stand for the whole count, so the heading never says "showing". A chart with one group
        // states no share: it would always be 100%.
        heading: dotGroupHeading({ label: g.label, shown: ratio && total != null ? total : shown, total, grandTotal: live.length > 1 ? grandTotal : null, unit }),
      }
    }),
  }
}

/**
 * A dot chart drawn from real counts alone (the endpoint lists no records for them): one dot per record while the whole fits in
 * `COUNT_DOT_CAP`, otherwise one dot per `dotRatio` records, stated in `dotMeans`. Null when every count is zero or missing.
 */
function countChart(
  title: string,
  source: string,
  unit: [string, string],
  groups: Array<{ key: string; label: string; count: number | null | undefined; tone?: DotTone }>,
): DotsSpec | null {
  const live = groups.filter((g) => (g.count ?? 0) > 0)
  const sum = live.reduce((a, g) => a + (g.count ?? 0), 0)
  if (sum <= 0) return null
  // Each group's left-over dot can take one more place than the division alone, so that room is kept free.
  const perDot = sum <= COUNT_DOT_CAP ? 1 : dotRatio(sum, COUNT_DOT_CAP - live.length)
  const { groups: g, grandTotal } = dotGroups(
    live.map((x) => ({ key: x.key, label: x.label, tone: x.tone, total: x.count ?? 0, dots: countDots(x.key, x.count ?? 0, perDot, unit) })),
    unit,
    true,
  )
  return {
    kind: 'dots',
    title,
    source,
    note: null,
    unit: unit[0],
    groups: g,
    drawn: g.reduce((a, x) => a + x.shown, 0),
    grandTotal,
    perDot,
    dotMeans: dotMeaning(perDot, unit),
  }
}

/** The four counts of public speakers on a data center item, or null when the table is not loaded or holds none for the scope. */
export function speakerCounts(res: DataCenterPositionsResponse | null | undefined): { for: number; against: number; question: number; neutral: number; total: number } | null {
  const t = res?.available ? res.totals : null
  if (!t || t.speakers_for == null || t.speakers_against == null || t.speakers_question == null) return null
  const neutral = t.speakers_neutral ?? 0
  const total = t.speakers_for + t.speakers_against + t.speakers_question + neutral
  return total > 0 ? { for: t.speakers_for, against: t.speakers_against, question: t.speakers_question, neutral, total } : null
}

const joinPlace = (name?: string | null, state?: string | null) => [name, state].filter(Boolean).join(', ') || null

function capNote(drawn: number, onRecord: number | null): string | null {
  if (onRecord != null && onRecord > drawn) return `Showing the most recent ${fmt(drawn)} of ${fmt(onRecord)}.`
  if (onRecord == null && drawn >= DOT_CAP) return `Showing the first ${fmt(DOT_CAP)} returned; there may be more.`
  return null
}

/** The dots for the key's chart, or null when there is nothing to draw (the round shows "No data available for this chart"). */
export function chartSpec(
  key: string,
  data: ChartData | null | undefined,
  place?: string | null,
  /** `meetings`: the meeting-mentions data drawn as meetings (one dot per meeting, or per several), not as passages. */
  view?: 'meetings',
): ChartSpec | null {
  if (!data) return null
  const dots = (title: string, source: string, unit: string, groups: GroupIn[], onRecord: number | null): DotsSpec | null => {
    const { groups: g, grandTotal } = dotGroups(groups)
    const drawn = g.reduce((a, x) => a + x.shown, 0)
    if (drawn <= 0) return null
    return { kind: 'dots', title, source, note: capNote(drawn, onRecord), unit, groups: g, drawn, grandTotal, perDot: 1, dotMeans: dotMeaning(1, [unit, `${unit}s`]) }
  }
  if (view === 'meetings') {
    return countChart(MEETINGS_TITLE, 'Open Navigator, local meeting recordings and transcripts', ['meeting', 'meetings'], [
      { key: 'meetings', label: 'Meetings where a data center came up', count: (data as DataCenterMeetingMentionsResponse).counts?.meetings },
    ])
  }
  switch (key as ChartKey) {
    case 'positions': {
      const c = speakerCounts(data as DataCenterPositionsResponse)
      if (!c) return null
      return countChart(CHART_TITLES.positions, 'Open Navigator, public comment in local meeting recordings', ['speaker', 'speakers'], [
        { key: 'for', label: 'Spoke for', count: c.for, tone: 'for' },
        { key: 'against', label: 'Spoke against', count: c.against, tone: 'against' },
        { key: 'question', label: 'Asked a question', count: c.question, tone: 'question' },
        { key: 'neutral', label: 'Took no side', count: c.neutral, tone: 'neutral' },
      ])
    }
    case 'job-claims': {
      const res = data as JobClaimsResponse
      const items = res.items ?? []
      const t = res.totals
      const on = t ? t.construction + t.operations : null
      const toDot = (c: (typeof items)[number]): Dot => ({
        id: c.job_claim_id,
        title: c.project_name ?? (c.speaker_role ? `Jobs claim, ${c.speaker_role}` : 'Jobs claim'),
        place: c.body_name ?? null,
        date: c.meeting_date ?? null,
        url: c.video_id ? `https://www.youtube.com/watch?v=${c.video_id}${c.start_seconds != null ? `&t=${Math.max(0, Math.floor(c.start_seconds))}s` : ''}` : null,
      })
      return dots(
        CHART_TITLES['job-claims'],
        'Open Navigator, claims quoted from meeting transcripts',
        'jobs claim',
        [
          { key: 'construction', label: 'Construction jobs', total: t?.construction ?? null, dots: items.filter((c) => c.phase === 'construction').map(toDot) },
          { key: 'operations', label: 'Operations jobs', total: t?.operations ?? null, dots: items.filter((c) => c.phase === 'operations').map(toDot) },
        ],
        on,
      )
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
      return countChart(
        CHART_TITLES.concerns,
        'Open Navigator, concerns found in meeting transcripts',
        ['mention', 'mentions'],
        [...list]
          .sort((a, b) => b.mention_count - a.mention_count || a.concern.localeCompare(b.concern))
          .map((c) => ({ key: c.concern, label: cap(concernLabel(c.concern)), count: c.mention_count })),
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
      // The endpoint counts projects for the whole scope but not per status, so a group states only what is drawn.
      const spec = dots(
        CHART_TITLES.projects,
        'Open Navigator, curated announcements and Epoch AI',
        'data center project',
        tally(items, (p) => statusLabel(p.status)).map((t) => ({
          key: t.key,
          label: t.key,
          dots: items
            .filter((p) => statusLabel(p.status) === t.key)
            .map((p) => ({ id: p.project_id, title: p.project_name, place: p.state_code ?? null, date: p.announced_on ?? null, url: p.source_url || null })),
        })),
        total,
      )
      return spec && total > items.length ? { ...spec, note: `Showing ${fmt(items.length)} of ${fmt(total)} projects.` } : spec
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
