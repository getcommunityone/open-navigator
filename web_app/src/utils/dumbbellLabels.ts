// #1264: placement for the compact (phone) dumbbell's value labels, printed directly above each dot. Pure, so the
// collision rules are unit-tested (dumbbellLabels.test.ts).

/** Approximate advance of one character of `.sc-micro` (the 11px mono used for the values), in px. */
export const MICRO_CHAR_W = 6.6

/** Width of a value label such as "30.5%", in px. */
export function labelWidth(text: string): number {
  return Math.ceil(text.length * MICRO_CHAR_W)
}

export interface LabelIn {
  /** The dot's x. */
  x: number
  /** The label's width. */
  width: number
}

export interface LabelOut {
  /** The label's centre (draw with text-anchor="middle"). */
  x: number
  /** True when there was no room beside the other label, so this one sits below the track instead of above it. */
  below: boolean
}

const clampCentre = (x: number, width: number, minX: number, maxX: number) => {
  const lo = minX + width / 2
  const hi = maxX - width / 2
  return hi < lo ? (minX + maxX) / 2 : Math.min(hi, Math.max(lo, x))
}

/**
 * Centres each label over its dot, kept inside [minX, maxX]. When the hollow dot's label (`a`) and the filled dot's
 * label (`b`) would overlap, they are pushed apart, each the same distance from the midpoint of their dots, in the
 * dots' own order. If the edges leave no room for both side by side, `a` goes below the track and both sit over
 * their dots again. A row with no `a` (a single value) places `b` alone.
 */
export function placeValueLabels(a: LabelIn | null, b: LabelIn, minX: number, maxX: number, gap = 4): { a: LabelOut | null; b: LabelOut } {
  const bAlone: LabelOut = { x: clampCentre(b.x, b.width, minX, maxX), below: false }
  if (!a) return { a: null, b: bAlone }
  let ax = clampCentre(a.x, a.width, minX, maxX)
  let bx = bAlone.x
  const need = (a.width + b.width) / 2 + gap
  if (Math.abs(ax - bx) >= need) return { a: { x: ax, below: false }, b: { x: bx, below: false } }
  // The dots' order decides which label goes left; equal dots put the earlier value (a) on the left.
  const aLeft = a.x <= b.x
  const mid = (a.x + b.x) / 2
  // Each label moves the same distance from the midpoint, by its own half-width plus half the gap.
  ax = aLeft ? mid - (a.width + gap) / 2 : mid + (a.width + gap) / 2
  bx = aLeft ? mid + (b.width + gap) / 2 : mid - (b.width + gap) / 2
  // Against an edge, slide the pair inward together.
  const left = Math.min(ax - a.width / 2, bx - b.width / 2)
  const right = Math.max(ax + a.width / 2, bx + b.width / 2)
  const shift = left < minX ? minX - left : right > maxX ? maxX - right : 0
  ax += shift
  bx += shift
  const fits = Math.min(ax - a.width / 2, bx - b.width / 2) >= minX - 0.5 && Math.max(ax + a.width / 2, bx + b.width / 2) <= maxX + 0.5
  if (fits) return { a: { x: ax, below: false }, b: { x: bx, below: false } }
  return { a: { x: clampCentre(a.x, a.width, minX, maxX), below: true }, b: bAlone }
}

/** Splits a row label into at most `maxLines` lines of about `maxChars` characters, at spaces; the last line ends in "…" if cut. */
export function wrapLabel(text: string, maxChars: number, maxLines = 2): string[] {
  const words = text.trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return ['']
  const lines: string[] = []
  let cur = ''
  for (const w of words) {
    const next = cur ? `${cur} ${w}` : w
    if (next.length <= maxChars || !cur) cur = next
    else {
      lines.push(cur)
      cur = w
    }
  }
  lines.push(cur)
  if (lines.length <= maxLines) return lines.map((l) => (l.length > maxChars ? `${l.slice(0, Math.max(1, maxChars - 1))}…` : l))
  const kept = lines.slice(0, maxLines)
  const last = kept[maxLines - 1]!
  kept[maxLines - 1] = `${last.slice(0, Math.max(1, maxChars - 1)).trimEnd()}…`
  return kept.map((l, i) => (i < maxLines - 1 && l.length > maxChars ? `${l.slice(0, Math.max(1, maxChars - 1))}…` : l))
}
