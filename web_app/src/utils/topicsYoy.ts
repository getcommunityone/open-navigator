// Browse all topics (#1343, #1361): which topics can be compared, their change, filtering by live story vs candidate
// topics, and the order and labels the dumbbell draws. Pure, so every rule is unit-tested (topicsYoy.test.ts). Nothing
// here invents a value: a topic the API marks as not comparable goes to "Too few meetings to compare" and is never given a change.
import type { YoyResponse, YoyTopic } from '../api/topicsYoy'

export type YoyMetric = 'share' | 'count'
export type YoyTopicFilter = 'all' | 'candidates' | 'stories'
export type YoySort = 'change' | 'latest'

export interface YoyRow {
  topic: YoyTopic
  a: number
  b: number
  /** Relative change, b / a − 1 (0.25 = +25%); null when a is 0. */
  change: number | null
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** The later year's label: "Jan–Nov 2026" when partial, "2026" when the year is complete, "2026 so far" when unknown. */
export function yearBLabel(d: Pick<YoyResponse, 'year_b' | 'year_b_through' | 'year_b_partial'>): string {
  if (!d.year_b_partial) return d.year_b
  const m = d.year_b_through ? Number(d.year_b_through.slice(5, 7)) : NaN
  if (!Number.isFinite(m) || m < 1 || m > 12) return `${d.year_b} so far`
  return m === 1 ? `Jan ${d.year_b}` : `Jan–${MONTHS[m - 1]} ${d.year_b}`
}

export function relChange(a: number, b: number): number | null {
  return a > 0 ? b / a - 1 : null
}

/** "+459%", "−20%", "0%" (a true minus sign); "—" when the change can't be computed. */
export function changeLabel(c: number | null): string {
  if (c == null || !Number.isFinite(c)) return '—'
  const pct = Math.round(c * 100)
  if (pct === 0) return '0%'
  return `${pct > 0 ? '+' : '−'}${Math.abs(pct).toLocaleString('en-US')}%`
}

export function parseTopicFilter(raw: string | null): YoyTopicFilter {
  if (raw === 'candidates' || raw === 'stories') return raw
  return 'all'
}

export function parseYoySort(raw: string | null): YoySort {
  return raw === 'latest' ? 'latest' : 'change'
}

export function filterTopics(topics: YoyTopic[], filter: YoyTopicFilter): YoyTopic[] {
  if (filter === 'candidates') return topics.filter((t) => !t.has_story)
  if (filter === 'stories') return topics.filter((t) => t.has_story)
  return topics
}

/** Comparable topics as rows for the metric and sort order, and the rest sorted by name. */
export function splitTopics(
  topics: YoyTopic[],
  metric: YoyMetric,
  sort: YoySort = 'change',
): { rows: YoyRow[]; tooFew: YoyTopic[] } {
  const rows: YoyRow[] = []
  const tooFew: YoyTopic[] = []
  for (const t of topics) {
    if (!t.comparable || t.share_a == null || t.share_b == null) {
      tooFew.push(t)
      continue
    }
    const a = metric === 'share' ? t.share_a : t.meetings_a
    const b = metric === 'share' ? t.share_b : t.meetings_b
    rows.push({ topic: t, a, b, change: relChange(a, b) })
  }
  rows.sort((x, y) =>
    sort === 'latest'
      ? y.b - x.b || (y.change ?? -Infinity) - (x.change ?? -Infinity) || x.topic.name.localeCompare(y.topic.name)
      : (y.change ?? -Infinity) - (x.change ?? -Infinity) || y.b - x.b || x.topic.name.localeCompare(y.topic.name),
  )
  tooFew.sort((x, y) => x.name.localeCompare(y.name))
  return { rows, tooFew }
}

/** `?state=&city=` for a link that keeps the page's place (empty at national scope). */
export function scopeQuery(stateCode?: string | null, city?: string | null): string {
  const q = new URLSearchParams()
  if (stateCode) {
    q.set('state', stateCode)
    if (city) q.set('city', city)
  }
  const s = q.toString()
  return s ? `?${s}` : ''
}

/** Live stories open at `/stories/<slug>`; candidate topics open in `/browse-topics?topic_id=<id>`, keeping place. */
export function topicDestination(
  topic: Pick<YoyTopic, 'topic_id' | 'slug' | 'has_story'>,
  stateCode?: string | null,
  city?: string | null,
): string {
  if (topic.has_story) return `/stories/${encodeURIComponent(topic.slug)}${scopeQuery(stateCode, city)}`
  const q = new URLSearchParams({ topic_id: String(topic.topic_id) })
  if (stateCode) {
    q.set('state', stateCode)
    if (city) q.set('city', city)
  }
  return `/browse-topics?${q.toString()}`
}
