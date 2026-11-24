import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from 'react'

/**
 * FLIP glide: when `signature` changes (new sort / group / metric), every `[data-flip]` child of `ref` that moved is
 * placed back at its old spot with a transform and then transitions to its new one (600 ms, ease-in-out).
 * Positions are measured with getBoundingClientRect relative to the container. Does nothing when `enabled` is false.
 */
export function useFlip(ref: RefObject<HTMLElement>, signature: string, enabled: boolean): void {
  const prev = useRef<Map<string, { x: number; y: number }>>(new Map())

  const measure = (root: HTMLElement) => {
    const base = root.getBoundingClientRect()
    const out = new Map<string, { x: number; y: number }>()
    root.querySelectorAll<HTMLElement>('[data-flip]').forEach((el) => {
      const r = el.getBoundingClientRect()
      out.set(el.dataset.flip!, { x: r.left - base.left, y: r.top - base.top })
    })
    return out
  }

  useLayoutEffect(() => {
    const root = ref.current
    if (!root) return
    const before = prev.current
    const after = measure(root)
    prev.current = after
    if (!enabled || before.size === 0) return
    const moved: HTMLElement[] = []
    root.querySelectorAll<HTMLElement>('[data-flip]').forEach((el) => {
      const a = before.get(el.dataset.flip!)
      const b = after.get(el.dataset.flip!)
      if (!a || !b) return
      const dx = a.x - b.x
      const dy = a.y - b.y
      if (Math.abs(dx) < 1 && Math.abs(dy) < 1) return
      el.style.transition = 'none'
      el.style.transform = `translate(${dx}px, ${dy}px)`
      moved.push(el)
    })
    if (!moved.length) return
    void root.offsetWidth // commit the inverted positions before releasing them
    for (const el of moved) {
      el.style.transition = 'transform var(--d-3) var(--ease-in-out)'
      el.style.transform = ''
      const done = () => {
        el.style.transition = ''
        el.removeEventListener('transitionend', done)
      }
      el.addEventListener('transitionend', done)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature, enabled])

  // Keep the stored positions fresh when the window is resized, so the next glide starts from where things really are.
  useEffect(() => {
    const onResize = () => {
      if (ref.current) prev.current = measure(ref.current)
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
}

/**
 * True for `ms` after `start` first becomes true (default: after mount) - the first-reveal window - and false afterwards or
 * when motion is reduced. Before `start` it stays true, so a chart below the fold keeps its "not yet revealed" state.
 */
export function useIntro(ms: number, reduced: boolean, start = true): boolean {
  const [on, setOn] = useState(!reduced)
  useEffect(() => {
    if (reduced || !start) return
    const id = window.setTimeout(() => setOn(false), ms)
    return () => window.clearTimeout(id)
  }, [ms, reduced, start, setOn])
  return on && !reduced
}
