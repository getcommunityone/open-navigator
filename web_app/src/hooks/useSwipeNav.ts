import { useEffect, useRef, type RefObject } from 'react'

/**
 * Swipe between a story's screens on a touch screen (#1222, owner 2026-11-26: "It should swipe left to toggle"): swipe left
 * = next screen, swipe right = previous. Shared by the Data Center Story and the topic stories.
 *
 * - Horizontal-dominant only: the finger must travel at least `minDistance` px sideways and clearly more sideways than up or
 *   down (`ratio`), within `maxMs`, so a vertical scroll (the phone's screen-by-screen snap) is never taken for a swipe and
 *   nothing calls preventDefault: the page keeps its own scrolling.
 * - Not inside something that pans or swipes on its own: maps, charts, sliders, form fields, dialogs, a horizontally
 *   scrollable strip, or anything marked `data-swipe-ignore` (see `SWIPE_IGNORE`).
 * - Touch only (`touchstart` / `touchend`): a mouse drag or a trackpad does nothing.
 */
export const SWIPE_IGNORE = [
  '[data-swipe-ignore]',
  '.stance-map',
  '.sc-block',
  '.leaflet-container',
  '.stance-place',
  'input',
  'select',
  'textarea',
  '[role="dialog"]',
  '[role="slider"]',
].join(', ')

export interface SwipeOptions {
  /** The element whose touches count (the story root). */
  rootRef: RefObject<HTMLElement>
  onNext: () => void
  onPrev: () => void
  /** False turns swiping off (a dialog is open, reduced layout, a wide screen). */
  enabled?: boolean
  minDistance?: number
  /** How much more sideways than vertical the gesture must be. */
  ratio?: number
  maxMs?: number
}

/** True when `el` (or an ancestor up to `root`) can scroll sideways itself, so a sideways drag belongs to it. */
function scrollsSideways(el: HTMLElement | null, root: HTMLElement): boolean {
  for (let n = el; n && n !== root && n !== document.body; n = n.parentElement) {
    if (n.scrollWidth > n.clientWidth + 1) {
      const ox = getComputedStyle(n).overflowX
      if (ox === 'auto' || ox === 'scroll') return true
    }
  }
  return false
}

/** Pure: which way a finished gesture goes, or null. Exported for the unit test. */
export function swipeDirection(dx: number, dy: number, ms: number, minDistance = 50, ratio = 1.5, maxMs = 800): 'next' | 'prev' | null {
  if (ms > maxMs || Math.abs(dx) < minDistance || Math.abs(dx) < ratio * Math.abs(dy)) return null
  return dx < 0 ? 'next' : 'prev'
}

export function useSwipeNav({ rootRef, onNext, onPrev, enabled = true, minDistance = 50, ratio = 1.5, maxMs = 800 }: SwipeOptions): void {
  const cb = useRef({ onNext, onPrev })
  cb.current = { onNext, onPrev }
  useEffect(() => {
    const root = rootRef.current
    if (!root || !enabled) return
    let start: { x: number; y: number; t: number } | null = null
    const onStart = (e: TouchEvent) => {
      start = null
      if (e.touches.length !== 1) return
      const target = e.target as HTMLElement | null
      if (target?.closest(SWIPE_IGNORE) || scrollsSideways(target, root)) return
      const t = e.touches[0]!
      start = { x: t.clientX, y: t.clientY, t: performance.now() }
    }
    const onEnd = (e: TouchEvent) => {
      if (!start) return
      const t = e.changedTouches[0]
      const s = start
      start = null
      if (!t) return
      const dir = swipeDirection(t.clientX - s.x, t.clientY - s.y, performance.now() - s.t, minDistance, ratio, maxMs)
      if (dir === 'next') cb.current.onNext()
      else if (dir === 'prev') cb.current.onPrev()
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
  }, [rootRef, enabled, minDistance, ratio, maxMs])
}
