// The small box visual every story screen carries (#1415): count boxes grouped by the screen's main category, so a particle
// flight (#1404) always has `[data-box]` marks to land on. A box is one real record, or (above MAX_BOXES) a stated number of
// records ("1 box = 5 meetings"); nothing is estimated and a zero is drawn as an empty state, never as invented boxes.
import type { TopicUpcomingResponse, UpcomingKind } from '../api/topicUpcoming'
import type { TopicOrganizationsResponse, OrgMatchMethod } from '../api/topicOrganizations'
import type { TopicLegislationResponse, TopicLocalActionsResponse, BillStatus } from '../api/topicPolicy'
import type { TopicSaidCounts } from '../api/topics'
import type { ChoiceGroup, StanceQuestion } from '../api/stance'
import { BOX_COLORS } from '../components/home/storyColors'
import { GROUP_COLORS } from './houseTheme'
import { choiceBars } from './storyQuestion'

export interface BoxGroup {
  key: string
  label: string
  count: number
  color: string
}

export interface BoxesSpec {
  /** The takeaway, in words ("37 of 45 counted speakers spoke against"). */
  title: string
  /** What one box stands for when each is a record ("meetings"). */
  unit: string
  groups: BoxGroup[]
  /** A line under the legend (what is and isn't drawn). */
  note?: string
}

/** The most boxes a strip draws: two rows on a phone. */
export const MAX_BOXES = 40

const fmt = (n: number) => n.toLocaleString('en-US')
const plural = (n: number, one: string, many = `${one}s`) => `${fmt(n)} ${n === 1 ? one : many}`

export interface BoxCell {
  key: string
  label: string
  color: string
}

/**
 * One cell per record when the total fits; otherwise each cell stands for `per` records and every non-empty group keeps at
 * least one cell. Largest remainders so the cells add up to the total's own share.
 */
export function allocateBoxes(groups: BoxGroup[], max = MAX_BOXES): { cells: BoxCell[]; per: number; total: number } {
  const live = groups.filter((g) => g.count > 0)
  const total = live.reduce((s, g) => s + g.count, 0)
  if (total <= 0) return { cells: [], per: 1, total: 0 }
  const per = total <= max ? 1 : Math.ceil(total / max)
  const raw = live.map((g) => g.count / per)
  const base = raw.map((r) => Math.max(1, Math.floor(r)))
  let left = Math.min(max, Math.ceil(total / per)) - base.reduce((a, b) => a + b, 0)
  const order = raw.map((r, i) => ({ i, rem: r - Math.floor(r) })).sort((a, b) => b.rem - a.rem)
  for (let k = 0; left > 0 && order.length > 0; k = (k + 1) % order.length, left--) base[order[k]!.i]! += 1
  const cells = live.flatMap((g, i) => Array.from({ length: base[i]! }, () => ({ key: g.key, label: g.label, color: g.color })))
  return { cells, per, total }
}

const group = (key: string, label: string, count: number | null | undefined, color: string): BoxGroup => ({ key, label, count: Math.max(0, count ?? 0), color })
const sum = (gs: BoxGroup[]) => gs.reduce((s, g) => s + g.count, 0)
const top = (gs: BoxGroup[]) => gs.reduce((b, g) => (g.count > b.count ? g : b), gs[0]!)

/** Public speakers counted by hand (who spoke up): for, against, asked a question, no side. */
export function positionsBoxes(
  totals: { speakers_for: number | null; speakers_against: number | null; speakers_question: number | null; speakers_neutral: number | null } | null | undefined,
  place: string,
): BoxesSpec | null {
  if (!totals) return null
  const gs = [
    group('for', 'Spoke for', totals.speakers_for, BOX_COLORS.for),
    group('against', 'Spoke against', totals.speakers_against, BOX_COLORS.against),
    group('question', 'Asked a question', totals.speakers_question, BOX_COLORS.question),
    group('neutral', 'Spoke, no side', totals.speakers_neutral, BOX_COLORS.meetings),
  ]
  const total = sum(gs)
  if (total === 0) return { title: `No public speaker is counted in ${place} yet`, unit: 'speakers', groups: gs }
  const t = top(gs)
  return { title: `${place}: ${fmt(t.count)} of ${plural(total, 'counted speaker')} ${t.label.toLowerCase()}`, unit: 'speakers', groups: gs }
}

const PROJECT_STATUS_COLOR: Record<string, string> = {
  Operating: BOX_COLORS.for,
  'Under construction': GROUP_COLORS[1]!,
  Planned: GROUP_COLORS[2]!,
  Cancelled: BOX_COLORS.against,
}

/** Data center projects or sites by their status (real rows tallied by their own status label). */
export function statusBoxes(rows: Array<{ key: string; count: number }>, noun: string, place: string): BoxesSpec {
  const gs = rows.map((r, i) => group(r.key, r.key, r.count, PROJECT_STATUS_COLOR[r.key] ?? GROUP_COLORS[(i + 3) % GROUP_COLORS.length]!))
  const total = sum(gs)
  if (total === 0) return { title: `No ${noun} on record in ${place}`, unit: noun, groups: gs }
  const t = top(gs)
  return { title: `${place}: ${plural(total, noun.replace(/s$/, ''))}, most ${t.label.toLowerCase()} (${fmt(t.count)})`, unit: noun, groups: gs }
}

/** Jobs claimed in meetings: construction against operations. */
export function jobClaimsBoxes(totals: { construction: number; operations: number } | null | undefined, place: string): BoxesSpec | null {
  if (!totals) return null
  const gs = [group('construction', 'Construction jobs claimed', totals.construction, GROUP_COLORS[2]!), group('operations', 'Operations jobs claimed', totals.operations, GROUP_COLORS[0]!)]
  const total = sum(gs)
  if (total === 0) return { title: `No job claim on record in ${place}`, unit: 'claims', groups: gs }
  return { title: `${place}: ${plural(total, 'job claim')} made in meetings`, unit: 'claims', groups: gs }
}

/** Sites over time: each box a site in the year's status columns, tallied across years. */
export function sitesTimelineBoxes(
  years: Array<{ operating: number; under_construction: number; planned: number; cancelled: number; no_longer_listed: number; status_not_published: number }> | null | undefined,
  place: string,
): BoxesSpec | null {
  if (!years) return null
  const s = (k: 'operating' | 'under_construction' | 'planned' | 'cancelled' | 'no_longer_listed' | 'status_not_published') => years.reduce((n, y) => n + (y[k] ?? 0), 0)
  const rows = [
    { key: 'Operating', count: s('operating') },
    { key: 'Under construction', count: s('under_construction') },
    { key: 'Planned', count: s('planned') },
    { key: 'Cancelled', count: s('cancelled') },
    { key: 'No longer listed', count: s('no_longer_listed') },
    { key: 'Status not published', count: s('status_not_published') },
  ].filter((r) => r.count > 0)
  return statusBoxes(rows, 'dated sites', place)
}

const ORG_METHOD: Array<{ key: OrgMatchMethod; label: string }> = [
  { key: 'named_in_meeting', label: 'Named in a meeting' },
  { key: 'keyword_in_mission', label: 'Mission names it' },
  { key: 'keyword_in_name', label: 'Name names it' },
  { key: 'ntee_code', label: 'IRS category' },
  { key: 'cause_tag', label: 'Cause tag' },
]

/** Nonprofits tied to the topic, grouped by how the record ties them. */
export function nonprofitsBoxes(res: TopicOrganizationsResponse | null | undefined, place: string): BoxesSpec | null {
  if (!res) return null
  const gs = ORG_METHOD.map((m, i) => group(m.key, m.label, res.counts?.[m.key], GROUP_COLORS[i % GROUP_COLORS.length]!)).filter((g) => g.count > 0)
  const total = sum(gs)
  if (total === 0) return { title: `No nonprofit is tied to this topic in ${place} yet`, unit: 'nonprofits', groups: [] }
  const t = top(gs)
  return { title: `${place}: ${plural(total, 'nonprofit')}, most tied by ${t.label.toLowerCase()} (${fmt(t.count)})`, unit: 'nonprofits', groups: gs }
}

const BILL_STATUS: Array<{ key: BillStatus; label: string; color: string }> = [
  { key: 'enacted', label: 'Enacted', color: BOX_COLORS.for },
  { key: 'passed_chamber', label: 'Passed one chamber', color: GROUP_COLORS[2]! },
  { key: 'pending', label: 'Pending', color: BOX_COLORS.meetings },
  { key: 'failed', label: 'Failed', color: BOX_COLORS.against },
]

/** State bills on a topic by how far they got: the chosen state's rows, else every state's (all years in our copy). */
export function billsBoxes(res: TopicLegislationResponse | null | undefined, place: string, stateCode?: string | null): BoxesSpec | null {
  if (!res) return null
  const rows = stateCode ? (res.summary ?? []).filter((r) => r.state_code === stateCode) : null
  const counts = (k: BillStatus) => (rows ? rows.filter((r) => r.status === k).reduce((n, r) => n + (r.bills ?? 0), 0) : (res.status_counts?.[k] ?? 0))
  const gs = BILL_STATUS.map((b) => group(b.key, b.label, counts(b.key), b.color))
  const total = sum(gs)
  const note = 'Bills from every year in our copy of OpenStates; the map below draws the recent years.'
  if (total === 0) return { title: `No state bill on this topic in ${place === 'National' ? 'our record' : place}`, unit: 'bills', groups: gs }
  const t = top(gs)
  return { title: `${place === 'National' ? 'Across America' : place}: ${plural(total, 'state bill')} on record, most ${t.label.toLowerCase()} (${fmt(t.count)})`, unit: 'bills', groups: gs, note }
}

/** What local bodies did in the meetings where they acted. */
export function actionsBoxes(res: TopicLocalActionsResponse | null | undefined, words: { advanced: string; blocked: string }, place: string): BoxesSpec | null {
  if (!res) return null
  const gs = [
    group('advanced', words.advanced, res.totals?.advanced, BOX_COLORS.for),
    group('blocked', words.blocked, res.totals?.blocked, BOX_COLORS.against),
    group('tabled_or_deferred', 'Put off', res.totals?.tabled_or_deferred, BOX_COLORS.meetings),
  ]
  const total = sum(gs)
  if (total === 0) return { title: `No local vote on this topic is read in ${place} yet`, unit: 'meetings', groups: gs }
  const t = top(gs)
  return { title: `${place}: bodies acted in ${plural(total, 'meeting')}; most often ${t.label.toLowerCase()} (${fmt(t.count)})`, unit: 'meetings', groups: gs }
}

/** The meetings the topic came up in, by the public's position (an AI reading of each transcript). */
export function saidBoxes(c: TopicSaidCounts | null | undefined, place: string): BoxesSpec | null {
  if (!c) return null
  const gs = [
    group('against', 'Public against', c.against, BOX_COLORS.against),
    group('for', 'Public for', c.for, BOX_COLORS.for),
    group('split', 'Public split', c.split, BOX_COLORS.question),
    group('silent', 'Public silent or unread', (c.silent ?? 0) + (c.unread ?? 0), BOX_COLORS.meetings),
    group('in_passing', 'Mentioned in passing', c.in_passing, BOX_COLORS.none),
  ]
  const total = sum(gs)
  if (total === 0) return { title: `No meeting is read for the public's position in ${place} yet`, unit: 'meetings', groups: gs }
  const t = top(gs)
  return { title: `${place}: ${plural(total, 'meeting')} read; most are ${t.label.toLowerCase()} (${fmt(t.count)})`, unit: 'meetings', groups: gs }
}

/** Decisions that name the topic against those that only mention it. */
export function decidedBoxes(d: { on_topic_total: number; in_passing_total: number } | null | undefined, place: string): BoxesSpec | null {
  if (!d) return null
  const gs = [group('on_topic', 'Names the policy', d.on_topic_total, GROUP_COLORS[0]!), group('in_passing', 'Mentioned in passing', d.in_passing_total, BOX_COLORS.none)]
  const total = sum(gs)
  if (total === 0) return { title: `No decision on this topic on record in ${place}`, unit: 'decisions', groups: gs }
  return { title: `${place}: ${fmt(d.on_topic_total)} of ${plural(total, 'decision')} name the policy`, unit: 'decisions', groups: gs }
}

/** The recap: what the record holds, one group per kind of record counted. */
export function recapBoxes(parts: Array<{ key: string; label: string; count: number | null | undefined }>, place: string): BoxesSpec | null {
  const gs = parts.filter((p) => p.count != null).map((p, i) => group(p.key, p.label, p.count, GROUP_COLORS[i % GROUP_COLORS.length]!))
  if (gs.length === 0) return null
  const total = sum(gs)
  if (total === 0) return { title: `Nothing on this topic is on record in ${place} yet`, unit: 'records', groups: gs }
  return { title: `${place}: ${gs.filter((g) => g.count > 0).map((g) => `${fmt(g.count)} ${g.label.toLowerCase()}`).join(', ')} on record`, unit: 'records', groups: gs }
}

/** How readers answered the story's question (the broadest group with enough answers), else the reader's own answer. */
export function verdictBoxes(
  groups: Array<ChoiceGroup | null | undefined>,
  options: StanceQuestion['options'] | undefined,
  yours: string | null,
  place: string,
): BoxesSpec | null {
  if (!options) return null
  for (const g of groups) {
    const bars = choiceBars(g, options)
    if (bars) {
      const gs = bars.map((b, i) => group(b.id, b.label, b.count, i === 0 ? GROUP_COLORS[0]! : i === 1 ? GROUP_COLORS[3]! : BOX_COLORS.meetings))
      const t = top(gs)
      return { title: `${place}: ${fmt(t.count)} of ${plural(sum(gs), 'reader answer')} chose "${t.label}"`, unit: 'answers', groups: gs }
    }
  }
  const mine = options.find((o) => o.id === yours)
  if (mine) return { title: 'Your answer is the one box so far; readers\' totals appear once enough have answered', unit: 'answers', groups: [group(mine.id, `Your answer: ${mine.label}`, 1, GROUP_COLORS[0]!)] }
  return { title: 'No reader answers are shown yet; answer to add the first box', unit: 'answers', groups: [] }
}

const KIND_COLOR: Record<UpcomingKind, string> = {
  meeting: GROUP_COLORS[0]!,
  hearing: GROUP_COLORS[3]!,
  bill_action: GROUP_COLORS[2]!,
  event: GROUP_COLORS[1]!,
  deadline: GROUP_COLORS[4]!,
}
export const UPCOMING_KIND_LABEL: Record<UpcomingKind, string> = {
  meeting: 'Scheduled meeting',
  hearing: 'Public hearing',
  bill_action: 'Bill action',
  event: 'Nonprofit event',
  deadline: 'Comment deadline',
}
export const upcomingKindColor = (k: UpcomingKind): string => KIND_COLOR[k] ?? BOX_COLORS.meetings

const DAY = 86_400_000
const at = (iso: string) => new Date(`${iso.slice(0, 10)}T12:00:00`).getTime()

export interface UpcomingStrip {
  /** 30, 60 or 90: the smallest window holding every dated item (90 when some fall later). */
  days: 30 | 60 | 90
  /** One column per week; each holds its items soonest first. */
  weeks: Array<{ start: string; items: Array<{ id: string; kind: UpcomingKind; date: string; title: string }> }>
  inWindow: number
  later: number
  /** The soonest item's date (ISO) or null. */
  next: string | null
}

/** Lay the upcoming items on a 30/60/90 day strip from the response's own `as_of` date. Pure: nothing is added. */
export function upcomingStrip(d: Pick<TopicUpcomingResponse, 'items' | 'as_of'>): UpcomingStrip {
  const start = at(d.as_of)
  const dated = d.items.filter((i) => Number.isFinite(at(i.date))).sort((a, b) => a.date.localeCompare(b.date))
  const farthest = dated.length ? Math.max(...dated.map((i) => Math.floor((at(i.date) - start) / DAY))) : 0
  const days: 30 | 60 | 90 = farthest <= 30 ? 30 : farthest <= 60 ? 60 : 90
  const nWeeks = Math.ceil(days / 7)
  const weeks: UpcomingStrip['weeks'] = Array.from({ length: nWeeks }, (_, w) => ({ start: new Date(start + w * 7 * DAY).toISOString().slice(0, 10), items: [] }))
  let later = 0
  for (const i of dated) {
    const off = Math.floor((at(i.date) - start) / DAY)
    if (off < 0) continue
    if (off >= days) {
      later += 1
      continue
    }
    weeks[Math.min(nWeeks - 1, Math.floor(off / 7))]!.items.push({ id: i.upcoming_id, kind: i.kind, date: i.date, title: i.title ?? i.body_name ?? UPCOMING_KIND_LABEL[i.kind] })
  }
  return { days, weeks, inWindow: dated.length - later, later, next: dated[0]?.date ?? null }
}
