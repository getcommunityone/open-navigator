import { useCallback, useEffect, useState } from 'react'
import usePrefersReducedMotion from '../../hooks/usePrefersReducedMotion'

/** How long a chart may sit inside the window, unrevealed, before it is drawn in its final state anyway. */
export const REVEAL_FALLBACK_MS = 1800

/** True when the element's box overlaps the window (ignores clipping by scrolling ancestors, unlike the observer). */
function inWindow(el: Element): boolean {
  if (typeof window === 'undefined') return false
  const r = el.getBoundingClientRect()
  if (r.width === 0 && r.height === 0) return false
  return r.bottom > 0 && r.right > 0 && r.top < window.innerHeight && r.left < window.innerWidth
}

/**
 * When a story chart plays its entrance (#1228), like the reference's `is-in` reveal: false until the chart scrolls into
 * view. A story screen on a phone scrolls inside its own block, and a tall chart may show only its first row when the
 * screen arrives. So the observer uses threshold 0 (any visible pixel counts), never a share of the chart.
 *
 * The chart is never left half-drawn. If the observer never fires (no IntersectionObserver, or a clipping ancestor it
 * cannot see past) but the chart has sat inside the window for `fallbackMs`, it is drawn in its final state. Under
 * prefers-reduced-motion it is always revealed, with no motion. A new `replayKey` (the scope) hides it again and replays
 * the entrance.
 */
export function useChartReveal<T extends Element>(replayKey?: unknown, { fallbackMs = REVEAL_FALLBACK_MS }: { fallbackMs?: number } = {}) {
  const reduced = usePrefersReducedMotion()
  const [el, setEl] = useState<T | null>(null)
  const [revealed, setRevealed] = useState(reduced)
  const ref = useCallback((node: T | null) => setEl(node), [])

  useEffect(() => {
    if (reduced) {
      setRevealed(true)
      return
    }
    setRevealed(false)
    if (!el) return
    let done = false
    let frame = 0
    const reveal = () => {
      if (done) return
      done = true
      // One frame at the start state first, so the transition has somewhere to run from.
      frame = requestAnimationFrame(() => setRevealed(true))
    }
    let io: IntersectionObserver | null = null
    if (typeof IntersectionObserver !== 'undefined') {
      io = new IntersectionObserver((es) => es.some((e) => e.isIntersecting) && reveal(), { threshold: 0 })
      io.observe(el)
    }
    // The safety net: poll the box against the window; once it has been inside long enough, draw the final state.
    let since: number | null = null
    const tick = window.setInterval(() => {
      if (done) return window.clearInterval(tick)
      if (typeof IntersectionObserver === 'undefined') return reveal()
      if (!inWindow(el)) {
        since = null
        return
      }
      since ??= Date.now()
      if (Date.now() - since >= fallbackMs) reveal()
    }, 300)
    return () => {
      done = true
      cancelAnimationFrame(frame)
      io?.disconnect()
      window.clearInterval(tick)
    }
  }, [el, reduced, replayKey, fallbackMs])

  return { ref, revealed: reduced || revealed, reduced }
}

export default useChartReveal
