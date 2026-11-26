/**
 * Splitting a state's boxes on the home box map by real speaker counts (#1087).
 *
 * Every figure here comes from the counts it is given: a state with no speakers gets no split, and the boxes always sum to
 * the state's own box total (largest-remainder rounding). Nothing is estimated.
 */

/** The speaker sides the home map splits by, in the order their bands are drawn. */
export const STANCE_ORDER = ['against', 'for', 'question', 'neutral'] as const
export type Stance = (typeof STANCE_ORDER)[number]

export interface StanceCounts {
  speakers_for: number
  speakers_against: number
  speakers_question: number
  speakers_neutral: number
}

export const stanceCount = (s: StanceCounts, k: Stance): number =>
  k === 'for' ? s.speakers_for : k === 'against' ? s.speakers_against : k === 'question' ? s.speakers_question : s.speakers_neutral

export const speakersOf = (s: StanceCounts | null | undefined): number =>
  s ? STANCE_ORDER.reduce((n, k) => n + Math.max(0, stanceCount(s, k) || 0), 0) : 0

/**
 * How many of `total` boxes each side gets, in proportion to its real count (largest remainder). A side with at least one
 * speaker gets at least one box when there are enough boxes for every such side, taken from the side with the most boxes.
 * Returns all zeros when there are no speakers or no boxes.
 */
export function splitBoxes(s: StanceCounts | null | undefined, total: number): Record<Stance, number> {
  const out: Record<Stance, number> = { against: 0, for: 0, question: 0, neutral: 0 }
  const sum = speakersOf(s)
  if (!s || sum <= 0 || total <= 0) return out
  const rem: Array<{ k: Stance; r: number; c: number }> = []
  let used = 0
  for (const k of STANCE_ORDER) {
    const c = Math.max(0, stanceCount(s, k) || 0)
    const q = (c / sum) * total
    out[k] = Math.floor(q)
    used += out[k]
    rem.push({ k, r: q - out[k], c })
  }
  // Largest remainder first; ties go to the larger count, then the drawing order (stable).
  rem.sort((a, b) => b.r - a.r || b.c - a.c)
  for (let i = 0; used < total; i = (i + 1) % rem.length) {
    out[rem[i]!.k] += 1
    used += 1
  }
  const nonzero = STANCE_ORDER.filter((k) => (stanceCount(s, k) || 0) > 0)
  if (total >= nonzero.length) {
    for (const k of nonzero) {
      if (out[k] > 0) continue
      const donor = STANCE_ORDER.reduce((a, b) => (out[b] > out[a] ? b : a))
      if (out[donor] <= 1) break
      out[donor] -= 1
      out[k] = 1
    }
  }
  return out
}

/**
 * The side of each box, in box order: `boxes` boxes filled band by band (against, for, question, neutral) from `splitBoxes`.
 * Sort the boxes (e.g. by x) before mapping so each side forms one contiguous band. Null for every box when there's no split.
 */
export function bandSides(s: StanceCounts | null | undefined, boxes: number): Array<Stance | null> {
  const split = splitBoxes(s, boxes)
  const out: Array<Stance | null> = []
  for (const k of STANCE_ORDER) for (let i = 0; i < split[k]; i++) out.push(k)
  while (out.length < boxes) out.push(null)
  return out
}
