/**
 * Which axis labels to print so none overlap: on a phone an eleven-year axis printed every year ran together
 * ("2016201720182019…"). The labels are evenly spaced `spacing` px apart; each is about `fontSize * 0.6` px per character
 * (the mono axis face) plus a gap. The step is the smallest of 1, 2, 5, 10, 20, 50… that keeps neighbours apart; the first
 * and the last label are always printed, and a stepped label too close to the last one is dropped instead. Nothing rotates.
 */
export const AXIS_CHAR_EM = 0.6
export const AXIS_LABEL_GAP = 6

export function labelWidth(chars: number, fontSize = 11): number {
  return fontSize * AXIS_CHAR_EM * chars
}

/** Indices (0..n-1) of the labels to print. */
export function pickAxisTicks(n: number, spacing: number, chars: number, fontSize = 11, gap = AXIS_LABEL_GAP): number[] {
  if (n <= 0) return []
  if (n === 1) return [0]
  const need = labelWidth(chars, fontSize) + gap
  const last = n - 1
  // Even the two ends would collide: print the last (the newest year, the end value) alone.
  if (last * spacing < need) return [last]
  let step = last
  for (let s = 1; s < last; s = s === 1 ? 2 : String(s)[0] === '2' ? (s / 2) * 5 : s * 2) {
    if (s * spacing >= need) {
      step = s
      break
    }
  }
  const out: number[] = []
  for (let i = 0; i < last; i += step) if (i === 0 || (last - i) * spacing >= need) out.push(i)
  out.push(last)
  return out
}

/** The years to label on a year axis drawn one slot per year across `plotWidth` px. */
export function pickYearTicks(years: readonly number[], plotWidth: number, fontSize = 11): number[] {
  if (!years.length) return []
  const spacing = plotWidth / years.length
  const chars = Math.max(...years.map((y) => String(y).length))
  return pickAxisTicks(years.length, spacing, chars, fontSize).map((i) => years[i]!)
}
