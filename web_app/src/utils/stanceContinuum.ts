// Where a reader sits after answering a story statement (#981). Pure: every figure comes from an API response, and a
// row is null (not guessed) when its data isn't there.
import type { GroupResult, StanceAnswer, StatementResults } from '../api/stance'
import { largestRemainder } from './matrixMapMath'

export interface ContinuumSegment {
  key: string
  label: string
  count: number
  /** Whole percent of the row (largest-remainder, so a row adds to 100). */
  percent: number
}

export interface ContinuumRow {
  /** "Readers in Texas", "Speakers at meetings across the country". */
  title: string
  /** Left to right. */
  segments: ContinuumSegment[]
  total: number
  /** Where "You" sits, 0–100 along the bar (the middle of the segment the answer belongs to). */
  marker: number
  /** One sentence in words, so the marker is never the only cue. */
  sentence: string
}

/** A row that hasn't reached the minimum sample: only the count so far is real. */
export interface ContinuumPending {
  title: string
  n: number
  minSample: number
}

const ANSWER_SEGMENTS: Array<{ key: StanceAnswer; label: string }> = [
  { key: 'agree', label: 'Agree' },
  { key: 'unsure', label: 'Not sure' },
  { key: 'disagree', label: 'Disagree' },
]

const plural = (n: number, one: string, many: string) => `${n.toLocaleString('en-US')} ${n === 1 ? one : many}`

function rowOf(parts: Array<{ key: string; label: string; count: number }>): { segments: ContinuumSegment[]; total: number } | null {
  const total = parts.reduce((a, p) => a + p.count, 0)
  if (total <= 0) return null
  const pct = largestRemainder(
    parts.map((p) => p.count),
    100,
  )
  return { segments: parts.map((p, i) => ({ ...p, percent: pct[i] ?? 0 })), total }
}

/** The middle of segment `key`, 0–100 along the bar. */
export function markerAt(segments: ContinuumSegment[], key: string): number {
  let start = 0
  for (const s of segments) {
    if (s.key === key) return Math.round((start + s.percent / 2) * 10) / 10
    start += s.percent
  }
  return 50
}

export interface ScopeNames {
  stateName: string | null
  city: string | null
}

/**
 * Readers' answers to the statement, from the most specific group that has reached the minimum sample (place, then
 * state, then country). When none has, the most specific group's count so far, so the page can say how many more are
 * needed. Null when there are no results at all.
 */
export function readersRow(
  results: StatementResults | null | undefined,
  minSample: number | null,
  answer: StanceAnswer | null,
  scope: ScopeNames,
): { row: ContinuumRow } | { pending: ContinuumPending } | null {
  if (!results) return null
  const groups: Array<{ title: string; where: string; group: GroupResult | null | undefined }> = [
    {
      title: scope.city && scope.stateName ? `Readers in ${scope.city}, ${scope.stateName}` : '',
      where: `in ${scope.city}, ${scope.stateName}`,
      group: scope.city ? results.place : null,
    },
    { title: scope.stateName ? `Readers in ${scope.stateName}` : '', where: `in ${scope.stateName}`, group: scope.stateName ? results.state : null },
    { title: 'Readers across the country', where: 'across the country', group: results.national },
  ]
  const ready = groups.find((g) => g.group?.available && g.title)
  if (ready?.group) {
    const g = ready.group
    const built = rowOf(ANSWER_SEGMENTS.map((s) => ({ ...s, count: (g[s.key] as number | null | undefined) ?? 0 })))
    if (!built) return null
    const mine = answer ? built.segments.find((s) => s.key === answer) : null
    return {
      row: {
        title: ready.title,
        ...built,
        marker: answer ? markerAt(built.segments, answer) : 50,
        // Names the group the bar uses (it may be wider than the story's place), and says only what the counts say.
        sentence: !mine
          ? `${plural(built.total, 'reader', 'readers')} ${ready.where} have answered.`
          : mine.count === 0
            ? `None of the ${plural(built.total, 'reader', 'readers')} ${ready.where} answered ${mine.label.toLowerCase()} so far.`
            : `${mine.percent}% of the ${plural(built.total, 'reader', 'readers')} ${ready.where} answered ${mine.label.toLowerCase()}, as you did.`,
      },
    }
  }
  const first = groups.find((g) => g.group && g.title)
  if (!first?.group) return null
  return { pending: { title: first.title, n: first.group.n, minSample: minSample ?? 0 } }
}

export interface SpeakerCounts {
  for: number
  against: number
  question: number
  neutral: number
}

/**
 * The people who spoke at meetings, from spoke for to spoke against, with the reader placed on the side their answer
 * lines up with. Only for a statement with a `lean` (agreeing lines up with speakers who spoke `for` or `against` data
 * centers): without one, mapping an answer onto speakers would be invented, so this is null. "Not sure" sits in the
 * middle, with the speakers who asked a question or took no side.
 */
export function speakersRow(
  counts: SpeakerCounts | null | undefined,
  lean: 'for' | 'against' | null | undefined,
  answer: StanceAnswer | null,
  placeLabel: string,
): ContinuumRow | null {
  if (!counts || !lean || !answer) return null
  const built = rowOf([
    { key: 'for', label: 'Spoke for', count: counts.for },
    { key: 'middle', label: 'Asked a question or took no side', count: counts.question + counts.neutral },
    { key: 'against', label: 'Spoke against', count: counts.against },
  ])
  if (!built) return null
  const side = answer === 'unsure' ? 'middle' : answer === 'agree' ? lean : lean === 'for' ? 'against' : 'for'
  const seg = built.segments.find((s) => s.key === side)!
  const who =
    side === 'middle'
      ? `the ${plural(seg.count, 'speaker', 'speakers')} (${seg.percent}%) who asked a question or took no side`
      : `the ${plural(seg.count, 'speaker', 'speakers')} (${seg.percent}%) who spoke ${side} data centers`
  return {
    title: `Speakers at meetings ${placeLabel}`,
    ...built,
    marker: markerAt(built.segments, side),
    sentence: `Your answer lines up with ${who}, of ${plural(built.total, 'speaker', 'speakers')} on record.`,
  }
}
