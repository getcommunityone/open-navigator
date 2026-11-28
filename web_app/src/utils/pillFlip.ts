/**
 * Subtle FLIP rearrange for the home topic pills (#1498), motion language from the owner's vizjb12 matrix
 * (same easing as boxFlight: cubic-bezier(0.7, 0, 0.2, 1), ~640 ms, small reading-order stagger). Design only —
 * no copied code from that project. Each pill keeps its identity and slides in a straight line to its new spot.
 */

export const PILL_FLIP_MS = 640
export const PILL_FLIP_STAGGER_MS = 28
export const PILL_FLIP_EASING = 'cubic-bezier(0.7, 0, 0.2, 1)'

type Rect = { left: number; top: number; width: number; height: number }

/** Snapshot each keyed element's viewport box before React reorders the DOM. */
export function captureFlipFirst(root: ParentNode | null, selector: string): Map<string, Rect> {
  const out = new Map<string, Rect>()
  if (!root) return out
  root.querySelectorAll<HTMLElement>(selector).forEach((el) => {
    const key = el.dataset.flipKey
    if (!key) return
    const r = el.getBoundingClientRect()
    out.set(key, { left: r.left, top: r.top, width: r.width, height: r.height })
  })
  return out
}

/**
 * After the new order is painted, invert each element from its first box to its last, then play to identity.
 * Returns a cleanup that cancels in-flight transitions (e.g. a newer sort supersedes this one).
 */
export function playFlipLast(
  root: ParentNode | null,
  selector: string,
  first: Map<string, Rect>,
  opts?: { reduced?: boolean },
): () => void {
  if (!root || first.size === 0 || opts?.reduced) return () => undefined
  const els = [...root.querySelectorAll<HTMLElement>(selector)].filter((el) => el.dataset.flipKey && first.has(el.dataset.flipKey))
  if (els.length === 0) return () => undefined

  const cleanups: Array<() => void> = []
  els.forEach((el, i) => {
    const key = el.dataset.flipKey!
    const a = first.get(key)!
    const b = el.getBoundingClientRect()
    const dx = a.left - b.left
    const dy = a.top - b.top
    if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) return

    const delay = Math.min(i * PILL_FLIP_STAGGER_MS, 260)
    el.style.transition = 'none'
    el.style.transform = `translate(${dx}px, ${dy}px)`
    // Force layout so the invert sticks before we play.
    void el.offsetWidth
    const onEnd = () => {
      el.style.transition = ''
      el.style.transform = ''
      el.removeEventListener('transitionend', onEnd)
    }
    el.addEventListener('transitionend', onEnd)
    el.style.transition = `transform ${PILL_FLIP_MS}ms ${PILL_FLIP_EASING} ${delay}ms`
    el.style.transform = 'translate(0, 0)'
    cleanups.push(() => {
      el.removeEventListener('transitionend', onEnd)
      el.style.transition = ''
      el.style.transform = ''
    })
  })

  return () => cleanups.forEach((c) => c())
}
