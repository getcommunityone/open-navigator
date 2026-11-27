import { HOUSE_THEME } from '../../utils/houseTheme'
import type { Stance } from '../../utils/boxSplit'
import { TOPIC_POSITIONS } from '../../utils/topicPositions'

/** Box colours: the house theme's segment colours (no red/green pair), a grey for meetings without a stance, the empty tint. */
export const BOX_COLORS: Record<Stance | 'meetings' | 'none', string> = {
  against: HOUSE_THEME.seg[3]!, // muted red
  for: HOUSE_THEME.seg[0]!, // teal
  question: HOUSE_THEME.seg[6]!, // a question takes no side: drawn as No side (#1110)
  neutral: HOUSE_THEME.seg[6]!, // plum
  meetings: '#9AA5A9',
  none: HOUSE_THEME.neutral,
}

export const STANCE_LABEL: Record<Stance, string> = {
  against: 'Spoke against',
  for: 'Spoke for',
  question: 'Asked a question',
  neutral: 'No side',
}

/** A colour mixed toward white by `amount` (0 = unchanged, 1 = white). */
export function tint(hex: string, amount: number): string {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim())
  if (!m) return hex
  const n = parseInt(m[1]!, 16)
  const mix = (c: number) => Math.round(c + (255 - c) * Math.min(1, Math.max(0, amount)))
  const out = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map(mix)
  return '#' + out.map((c) => c.toString(16).padStart(2, '0')).join('').toUpperCase()
}

/**
 * #1117: an area with no counted speakers where Jev (an AI classifier) read the public as mostly opposed in at least one
 * meeting: a lighter tint of the Spoke against colour, so it reads as related to, but not the same as, counted speakers.
 */
export const PUBLIC_AGAINST_COLOR = tint(BOX_COLORS.against, 0.45)
/** #1117: the outline around an area where Jev read officials as siding against the public. */
export const DISAGREEMENT_STROKE = '#1c1917'
// Only the data center maps draw this tint (the speaker maps), so it takes that topic's words (#1200).
export const PUBLIC_AGAINST_LABEL = `${TOPIC_POSITIONS['data-centers']!.against} (AI reading of meetings)`
export const DISAGREEMENT_LABEL = 'Officials sided against the public'

/** Jev's two served meeting counts for an area (#1117); missing means 0. */
export interface LeanCounts {
  public_against_meetings?: number | null
  disagreement_meetings?: number | null
}

const count = (n: number | null | undefined) => Math.max(0, n || 0)

/**
 * The hover line for an area's AI reading, or null when both counts are 0: "AI reading: the public mostly opposed in 3
 * meetings; officials sided against the public in 1." Supported and mixed readings are never served, so never shown.
 */
export function leanLine(l: LeanCounts | null | undefined): string | null {
  const pa = count(l?.public_against_meetings)
  const dis = count(l?.disagreement_meetings)
  const m = (n: number) => `${n.toLocaleString('en-US')} ${n === 1 ? 'meeting' : 'meetings'}`
  const parts: string[] = []
  if (pa > 0) parts.push(`the public mostly opposed in ${m(pa)}`)
  if (dis > 0) parts.push(`officials sided against the public in ${m(dis)}`)
  return parts.length ? `AI reading: ${parts.join('; ')}.` : null
}

/** The fill for an area's dots or boxes that have no stance band: the AI-reading tint, else `fallback` (grey or empty). */
export function leanFill(l: LeanCounts | null | undefined, fallback: string): string {
  return count(l?.public_against_meetings) > 0 ? PUBLIC_AGAINST_COLOR : fallback
}

/** True when the area should carry the disagreement outline. */
export const hasDisagreement = (l: LeanCounts | null | undefined) => count(l?.disagreement_meetings) > 0
