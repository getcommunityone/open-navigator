// Words and pure helpers for a topic's policy charts (#1274): the state legislation map, the public-position breakdown
// and the local-actions tracker. Every count these charts show comes from the API (our bills and our meetings); the words
// here only name what the data already says. Decision record: web_docs/docs/development/topic-legislation-map.md.
import type { ActionCounts, ActionGroup, BillStatus, LegislationSummaryRow } from '../api/topicPolicy'

/** Most advanced first: a state's colour is the first status any of its (filtered) bills reached. */
export const STATUS_ORDER: readonly BillStatus[] = ['enacted', 'passed_chamber', 'pending', 'failed']

export const STATUS_LABEL: Record<BillStatus, string> = {
  enacted: 'Enacted',
  passed_chamber: 'Passed one chamber',
  pending: 'Introduced, pending',
  failed: 'Failed or died',
}

/** Map fills: one hue, darker = further along; failed is neutral grey; a state with no bill stays paper. */
export const STATUS_FILL: Record<BillStatus, string> = {
  enacted: 'color-mix(in srgb, var(--violet) 62%, var(--ink))',
  passed_chamber: 'var(--violet)',
  pending: 'color-mix(in srgb, var(--violet) 45%, var(--paper))',
  failed: 'var(--neutral-data)',
}
export const NO_BILL_FILL = 'var(--paper-raised)'

/** The most advanced status among some rows, or null when there are none. */
export function topStatus(rows: { status: BillStatus }[]): BillStatus | null {
  for (const s of STATUS_ORDER) if (rows.some((b) => b.status === s)) return s
  return null
}

export interface BillFilter {
  /** Only bills whose latest action is in this year or later (null = every year). */
  sinceYear: number | null
  /** Only bills in this category (null = every category). */
  category: string | null
}

export function filterRows(rows: LegislationSummaryRow[], f: BillFilter): LegislationSummaryRow[] {
  return rows.filter(
    (r) =>
      r.bills > 0 &&
      (f.category == null || r.category === f.category) &&
      (f.sinceYear == null || (r.year != null && Number(r.year) >= f.sinceYear)),
  )
}

export interface StateShade {
  state_code: string
  state: string | null
  status: BillStatus
  bills: number
}

/** Each state's status (the furthest any filtered bill got) and bill count; states left with no bill are dropped. */
export function shadeStates(rows: LegislationSummaryRow[], f: BillFilter): StateShade[] {
  const by = new Map<string, { state: string | null; rows: LegislationSummaryRow[] }>()
  for (const r of filterRows(rows, f)) {
    const g = by.get(r.state_code) ?? { state: r.state, rows: [] }
    g.rows.push(r)
    by.set(r.state_code, g)
  }
  const out: StateShade[] = []
  for (const [code, g] of by) {
    const status = topStatus(g.rows)
    if (status) out.push({ state_code: code, state: g.state, status, bills: g.rows.reduce((n, r) => n + r.bills, 0) })
  }
  return out.sort((a, b) => a.state_code.localeCompare(b.state_code))
}

/** States per status, for the legend counts. */
export function countByStatus(shades: StateShade[]): Record<BillStatus, number> {
  const c: Record<BillStatus, number> = { enacted: 0, passed_chamber: 0, pending: 0, failed: 0 }
  for (const s of shades) c[s.status] += 1
  return c
}

/** Earliest and latest year among the rows (strings on the wire), or null when none has a year. */
export function yearSpan(rows: LegislationSummaryRow[]): [number, number] | null {
  let lo = Infinity
  let hi = -Infinity
  for (const r of rows) {
    if (r.year == null) continue
    const y = Number(r.year)
    if (y < lo) lo = y
    if (y > hi) hi = y
  }
  return Number.isFinite(lo) ? [lo, hi] : null
}

/** Bills per category among the filtered rows (for the direction menu). */
export function countByCategory(rows: LegislationSummaryRow[], sinceYear: number | null): Map<string, number> {
  const m = new Map<string, number>()
  for (const r of filterRows(rows, { sinceYear, category: null })) m.set(r.category, (m.get(r.category) ?? 0) + r.bills)
  return m
}

// ---------------------------------------------------------------------------------------------------------------
// Public positions in meetings
// ---------------------------------------------------------------------------------------------------------------

export type PositionSide = 'support' | 'neutral' | 'oppose'

export interface PositionStyle {
  label: string
  side: PositionSide
  /** Stronger (1) or milder (0) end of its side, for the fill's depth. */
  strong: boolean
}

/** The five positions water fluoridation's meeting reading uses (llm.typesafe.topic_lean), in plain words. */
export const FIVE_POSITION_STYLE: Record<string, PositionStyle> = {
  support_require_all: { label: 'Support, require everywhere', side: 'support', strong: true },
  support_local_choice: { label: 'Support, each community decides', side: 'support', strong: false },
  no_opinion: { label: 'No opinion', side: 'neutral', strong: false },
  oppose_local_choice: { label: 'Oppose, each community decides', side: 'oppose', strong: false },
  oppose_ban_all: { label: 'Oppose, ban everywhere', side: 'oppose', strong: true },
}

/** The shared lean labels every other topic uses. */
export const LEAN_POSITION_STYLE: Record<string, PositionStyle> = {
  mostly_supportive: { label: 'Mostly for', side: 'support', strong: true },
  mixed: { label: 'Split', side: 'neutral', strong: false },
  mostly_opposed: { label: 'Mostly against', side: 'oppose', strong: true },
}

export function positionStyle(key: string): PositionStyle {
  return FIVE_POSITION_STYLE[key] ?? LEAN_POSITION_STYLE[key] ?? { label: key.replace(/_/g, ' '), side: 'neutral', strong: false }
}

export function positionFill(p: PositionStyle): string {
  if (p.side === 'neutral') return 'var(--neutral-data)'
  const base = p.side === 'support' ? 'var(--violet)' : 'var(--vermilion)'
  return p.strong ? base : `color-mix(in srgb, ${base} 55%, var(--paper))`
}

/** n of total as a whole percent, or null when total is 0 (never a made-up share). */
export function pct(n: number, total: number): number | null {
  return total > 0 ? Math.round((n / total) * 100) : null
}

// ---------------------------------------------------------------------------------------------------------------
// Local actions
// ---------------------------------------------------------------------------------------------------------------

export const ACTION_ORDER: readonly ActionGroup[] = ['advanced', 'blocked', 'tabled_or_deferred']

export const ACTION_FILL: Record<ActionGroup, string> = {
  advanced: 'var(--violet)',
  blocked: 'var(--vermilion)',
  tabled_or_deferred: 'var(--ink-3)',
}

const GENERIC_ACTION_LABEL: Record<ActionGroup, string> = {
  advanced: 'Voted to move it forward',
  blocked: 'Voted to stop or limit it',
  tabled_or_deferred: 'Tabled or put off',
}

/** Per-topic words for the three outcome groups, restating the question the meeting reading asked. */
const TOPIC_ACTION_LABEL: Record<string, Record<ActionGroup, string>> = {
  'water-fluoridation': {
    advanced: 'Voted to keep or start fluoridation',
    blocked: 'Voted to end fluoridation',
    tabled_or_deferred: 'Tabled, deferred or sent to voters',
  },
}

export function actionLabels(topic: string): Record<ActionGroup, string> {
  return TOPIC_ACTION_LABEL[topic] ?? GENERIC_ACTION_LABEL
}

export function actionTotal(c: ActionCounts): number {
  return c.advanced + c.blocked + c.tabled_or_deferred
}
