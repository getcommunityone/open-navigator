// The home hero's topic pills (#1416): every topic that is hot or trending for the page's place, not only the hand-curated
// live stories. Pure, from the catalog's live stories and one `GET /api/topics/yoy?state=&city=` response, so the
// ordering, the badges and the scope are unit-tested (hotTopics.test.ts). Nothing here invents a number: a topic is
// "rising" only when the API marks it comparable (its minimum meeting counts) and its share of meetings grew; "heated"
// only when the API gave a mean heat (at least `min_heat_rated` classifier-rated public speakers).
import type { YoyResponse, YoyTopic } from '../api/topicsYoy'
import { relChange } from './topicsYoy'

/** A topic's meeting share must grow by at least this (0.25 = +25%) to count as rising. */
export const RISE_MIN = 0.25
/** Rises above this saturate the rise score, so one 4x outlier cannot bury every heated topic. */
export const RISE_CAP = 3
/** Mean heat (1-5) at or above this is "heated": the middle of the scale. */
export const HEAT_MIN = 3
export const MAX_RISING = 8
export const MAX_HEATED = 6

export interface HotPill {
  /** `?topic=` value: the topic's slug (query_id). */
  id: string
  title: string
  /** civicsearch_topic id; null for a live story the yoy response does not carry. */
  topicId: number | null
  /** The topic has a data story (from the catalog's live list). */
  live: boolean
  /** Relative change in the share of meetings (0.4 = +40%) when rising, else null. */
  rise: number | null
  /** Mean classifier heat (1-5) when heated, else null. */
  heat: number | null
  /** Rated speakers behind `heat`. */
  heatRated: number
  /** 0-2: rise score plus heat score; 0 for a live story that is neither. */
  score: number
  /** Meetings that discussed it this year (tie-break), 0 when unknown. */
  meetings: number
}

export interface LiveChip {
  id: string
  title: string
}

const clamp01 = (n: number) => Math.min(1, Math.max(0, n))
const riseScore = (rise: number | null) => (rise == null ? 0 : clamp01(rise / RISE_CAP))
const heatScore = (heat: number | null) => (heat == null ? 0 : clamp01((heat - 1) / 4))

/** A topic's rise in its share of meetings, or null when it is not rising (not comparable, no share, or under RISE_MIN). */
export function topicRise(t: YoyTopic): number | null {
  if (!t.comparable || t.share_a == null || t.share_b == null) return null
  const c = relChange(t.share_a, t.share_b)
  return c != null && c >= RISE_MIN ? c : null
}

/** A topic's heat when heated (mean given by the API and at or above HEAT_MIN), else null. */
export function topicHeated(t: YoyTopic): number | null {
  const h = t.heat_mean
  return typeof h === 'number' && Number.isFinite(h) && h >= HEAT_MIN ? h : null
}

/**
 * The pills for a place: every live story, plus the top rising topics, plus the most heated topics, ordered by the
 * combined score (rise + heat, each 0-1) so a topic both rising and heated leads. Ties go to live stories, then to the
 * topic discussed in more meetings, then by name. Live stories keep their place in the row even with no signal (score 0).
 * With no yoy data (loading, failed) the row is just the live stories in the catalog's order.
 */
export function buildHotPills(live: LiveChip[], yoy: YoyResponse | null | undefined): HotPill[] {
  const liveIds = new Set(live.map((s) => s.id))
  const byId = new Map<string, HotPill>()
  const order = new Map<string, number>()
  live.forEach((s, i) => {
    order.set(s.id, i)
    byId.set(s.id, { id: s.id, title: s.title, topicId: null, live: true, rise: null, heat: null, heatRated: 0, score: 0, meetings: 0 })
  })
  const topics = yoy?.topics ?? []
  const rising = topics
    .map((t) => ({ t, rise: topicRise(t) }))
    .filter((x): x is { t: YoyTopic; rise: number } => x.rise != null)
    .sort((a, b) => b.rise - a.rise || b.t.meetings_b - a.t.meetings_b)
    .slice(0, MAX_RISING)
  const heated = topics
    .map((t) => ({ t, heat: topicHeated(t) }))
    .filter((x): x is { t: YoyTopic; heat: number } => x.heat != null)
    .sort((a, b) => b.heat - a.heat || (b.t.heat_rated ?? 0) - (a.t.heat_rated ?? 0))
    .slice(0, MAX_HEATED)
  const touch = (t: YoyTopic): HotPill => {
    const cur =
      byId.get(t.slug) ??
      ({ id: t.slug, title: t.name, topicId: t.topic_id, live: liveIds.has(t.slug), rise: null, heat: null, heatRated: 0, score: 0, meetings: 0 } as HotPill)
    cur.topicId = t.topic_id
    cur.meetings = t.meetings_b
    byId.set(t.slug, cur)
    return cur
  }
  for (const { t, rise } of rising) touch(t).rise = rise
  for (const { t, heat } of heated) {
    const p = touch(t)
    p.heat = heat
    p.heatRated = t.heat_rated ?? 0
  }
  // A live story carries its own yoy facts (ids, meetings) even when neither rising nor heated.
  for (const t of topics) if (liveIds.has(t.slug)) touch(t)
  const pills = [...byId.values()]
  for (const p of pills) p.score = riseScore(p.rise) + heatScore(p.heat)
  return pills.sort(
    (a, b) =>
      b.score - a.score ||
      Number(b.live) - Number(a.live) ||
      b.meetings - a.meetings ||
      (order.get(a.id) ?? 1e9) - (order.get(b.id) ?? 1e9) ||
      a.title.localeCompare(b.title),
  )
}

/** How the home topic pills are ordered (#1498). Default `hot` = combined rise+heat score (buildHotPills). */
export type PillSort = 'hot' | 'heat' | 'trending'

export function parsePillSort(raw: string | null | undefined): PillSort {
  const v = (raw ?? '').trim().toLowerCase()
  if (v === 'heat' || v === 'trending') return v
  return 'hot'
}

/**
 * Reorder built pills for the user's sort (#1498). `hot` keeps buildHotPills order. `heat` puts the hottest first
 * (unheated live stories after, catalog order). `trending` puts the biggest rises first (non-rising after).
 */
export function sortHotPills(pills: HotPill[], mode: PillSort): HotPill[] {
  if (mode === 'hot' || pills.length < 2) return pills
  const copy = [...pills]
  if (mode === 'heat') {
    return copy.sort(
      (a, b) =>
        (b.heat ?? -1) - (a.heat ?? -1) ||
        b.heatRated - a.heatRated ||
        Number(b.live) - Number(a.live) ||
        b.meetings - a.meetings ||
        a.title.localeCompare(b.title),
    )
  }
  // trending
  return copy.sort(
    (a, b) =>
      (b.rise ?? -1) - (a.rise ?? -1) ||
      Number(b.live) - Number(a.live) ||
      b.meetings - a.meetings ||
      a.title.localeCompare(b.title),
  )
}

/** The text a pill's badges add for a screen reader and a tooltip ("rising, up 62% in share of meetings; heated, 3.7 of 5"). */
export function pillBadgeText(p: Pick<HotPill, 'rise' | 'heat' | 'heatRated'>): string {
  const out: string[] = []
  if (p.rise != null) out.push(`rising: its share of meetings is up ${Math.round(p.rise * 100)}% on last year`)
  if (p.heat != null) out.push(`heated: speakers rated it ${p.heat.toFixed(1)} of 5 (${p.heatRated.toLocaleString('en-US')} rated)`)
  return out.join('; ')
}
