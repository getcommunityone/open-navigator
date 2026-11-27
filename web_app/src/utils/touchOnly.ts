/** True on a device whose main pointer can't hover or is a finger (a phone or tablet), so hints say "Tap", not "Hover"
 *  (#1057), and the story maps drill on a tap with no card (#1277). */
export function isTouchOnly(): boolean {
  try {
    return typeof window !== 'undefined' && !!window.matchMedia?.('(hover: none), (pointer: coarse)').matches
  } catch {
    return false
  }
}

/**
 * True when the reader asked for less motion or less data (#1277): `prefers-reduced-motion: reduce`, `prefers-reduced-data:
 * reduce`, or the browser's Save-Data hint. The map hover card then shows the recording's still image instead of playing it.
 */
export function prefersStillMedia(): boolean {
  try {
    if (typeof window === 'undefined') return false
    const mq = (q: string) => !!window.matchMedia?.(q).matches
    if (mq('(prefers-reduced-motion: reduce)') || mq('(prefers-reduced-data: reduce)')) return true
    const conn = (typeof navigator !== 'undefined' ? (navigator as Navigator & { connection?: { saveData?: boolean } }).connection : undefined)
    return !!conn?.saveData
  } catch {
    return false
  }
}
