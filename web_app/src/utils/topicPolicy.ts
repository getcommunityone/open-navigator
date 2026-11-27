// Words and pure helpers for a topic's policy charts (#1274): the state legislation map, the public-position breakdown
// and the local-actions tracker. Every count these charts show comes from the API (our bills and our meetings); the words
// here only name what the data already says. Decision record: web_docs/docs/development/topic-legislation-map.md.
import type { ActionCounts, ActionGroup, BillStatus, LegislationBill, LegislationState } from '../api/topicPolicy'

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

/** The most advanced status among some bills, or null when there are none. */
export function topStatus(bills: Pick<LegislationBill, 'status'>[]): BillStatus | null {
  for (const s of STATUS_ORDER) if (bills.some((b) => b.status === s)) return s
  return null
}

export interface BillFilter {
  /** Only bills whose latest action is in this year or later (null = every year). */
  sinceYear: number | null
  /** Only bills in this category (null = every category). */
  category: string | null
}

export function filterBills(bills: LegislationBill[], f: BillFilter): LegislationBill[] {
  return bills.filter(
    (b) =>
      (f.category == null || b.category === f.category) &&
      (f.sinceYear == null || (b.year != null && Number(b.year) >= f.sinceYear)),
  )
}

export interface StateShade {
  state_code: string
  state: string | null
  status: BillStatus
  bills: LegislationBill[]
}

/** Each state's filtered bills and the status that colours it; states left with no bill are dropped. */
export function shadeStates(states: LegislationState[], f: BillFilter): StateShade[] {
  const out: StateShade[] = []
  for (const s of states) {
    const bills = filterBills(s.bills, f)
    const status = topStatus(bills)
    if (status) out.push({ state_code: s.state_code, state: s.state, status, bills: sortBills(bills) })
  }
  return out
}

/** Within a state: most advanced status first, then newest action. */
export function sortBills(bills: LegislationBill[]): LegislationBill[] {
  return [...bills].sort(
    (a, b) =>
      STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status) ||
      (b.last_action_date ?? '').localeCompare(a.last_action_date ?? '') ||
      (a.identifier ?? '').localeCompare(b.identifier ?? ''),
  )
}

/** States per status, for the legend counts. */
export function countByStatus(shades: StateShade[]): Record<BillStatus, number> {
  const c: Record<BillStatus, number> = { enacted: 0, passed_chamber: 0, pending: 0, failed: 0 }
  for (const s of shades) c[s.status] += 1
  return c
}

/** Earliest and latest year among the bills (strings on the wire), or null when no bill has a year. */
export function yearSpan(states: LegislationState[]): [number, number] | null {
  let lo = Infinity
  let hi = -Infinity
  for (const s of states)
    for (const b of s.bills) {
      if (b.year == null) continue
      const y = Number(b.year)
      if (y < lo) lo = y
      if (y > hi) hi = y
    }
  return Number.isFinite(lo) ? [lo, hi] : null
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
