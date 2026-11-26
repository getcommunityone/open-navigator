/** True on a device whose main pointer can't hover (a phone or tablet), so hints say "Tap", not "Hover" (#1057). */
export function isTouchOnly(): boolean {
  try {
    return typeof window !== 'undefined' && !!window.matchMedia?.('(hover: none)').matches
  } catch {
    return false
  }
}
