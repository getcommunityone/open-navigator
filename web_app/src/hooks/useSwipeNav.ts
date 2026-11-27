import { useEffect, useRef, type RefObject } from 'react'

/** The shortest horizontal travel, in CSS pixels, that counts as a swipe. */
export const SWIPE_MIN_PX = 50
/** A swipe is mostly sideways: its horizontal travel is at least this many times its vertical travel. */
export const SWIPE_RATIO = 1.5
/** A swipe is a flick, not a slow drag (a drag is someone reading or selecting). */
export const SWIPE_MAX_MS = 800

/** Where the gesture belongs to the control under the finger, not to the story. */
const OWN_TOUCH = 'input, select, textarea, [contenteditable="true"], [data-keys-own], [data-swipe-own], [role="dialog"], [role="slider"], .stance-place'

/** Which way a finished touch moves the story: `next` for a swipe to the left, `prev` to the right, else null. */
export function swipeDirection(dx: number, dy: number, ms: number): 'next' | 'prev' | null {
  if (ms > SWIPE_MAX_MS) return null
  if (Math.abs(dx) < SWIPE_MIN_PX || Math.abs(dx) < Math.abs(dy) * SWIPE_RATIO) return null
  return dx < 0 ? 'next' : 'prev'
}

/** True when an element between `el` and `root` scrolls sideways itself (a wide table, a chart strip): it keeps the swipe. */
function scrollsSideways(el: Element | null, root: Element): boolean {
  for (let n = el; n && n !== root; n = n.parentElement) {
    if (n.scrollWidth > n.clientWidth + 1) {
      const ox = getComputedStyle(n).overflowX
      if (ox === 'auto' || ox === 'scroll') return true
    }
  }
  return false
}

interface Options {
  rootRef: RefObject<HTMLElement>
  onNext: () => void
  onPrev: () => void
  /** False while a dialog owns the page. */
  enabled?: boolean
}

/**
 * Swipe left for the next screen and right for the previous one (#1224), on a touch screen. Vertical scrolling and scroll
 * snap are untouched (the listeners are passive and never prevent the default): only a quick, mostly sideways flick that
 * starts outside a control, a dialog or anything that scrolls sideways itself moves the story, through the same function as
 * Next and the arrow keys.
 */
export function useSwipeNav(opts: Options) {
  const o = useRef(opts)
  o.current = opts
  useEffect(() => {
    const root = opts.rootRef.current
    if (!root) return
    let start: { x: number; y: number; t: number } | null = null
    const onStart = (e: TouchEvent) => {
      start = null
      if (o.current.enabled === false || e.touches.length !== 1) return
      const t = e.target as Element | null
      if (t?.closest?.(OWN_TOUCH) || scrollsSideways(t, root)) return
      const p = e.touches[0]!
      start = { x: p.clientX, y: p.clientY, t: Date.now() }
    }
    const onEnd = (e: TouchEvent) => {
      const s = start
      start = null
      if (!s || o.current.enabled === false) return
      const p = e.changedTouches[0]
      if (!p) return
      const dir = swipeDirection(p.clientX - s.x, p.clientY - s.y, Date.now() - s.t)
      if (dir === 'next') o.current.onNext()
      else if (dir === 'prev') o.current.onPrev()
    }
    const onCancel = () => (start = null)
    root.addEventListener('touchstart', onStart, { passive: true })
    root.addEventListener('touchend', onEnd, { passive: true })
    root.addEventListener('touchcancel', onCancel, { passive: true })
    return () => {
      root.removeEventListener('touchstart', onStart)
      root.removeEventListener('touchend', onEnd)
      root.removeEventListener('touchcancel', onCancel)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opts.rootRef.current])
}
