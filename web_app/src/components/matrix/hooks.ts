import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState, type RefObject } from 'react'
import { parseOff, toggleSeries, writeOff } from '../../utils/matrixTable'
import type { MatrixCtx, SectionId } from './types'

/** What a section tells its figure: has the section entered view yet, and the section element (for scroll-scrubbed charts). */
export const SectionContext = createContext<{ seen: boolean; el: HTMLElement | null }>({ seen: true, el: null })
export const useSection = () => useContext(SectionContext)

/** True once the element has been at least `threshold` visible. Stays true (each section animates in once). */
export function useInViewOnce(ref: RefObject<Element>, threshold = 0.12): boolean {
  const [seen, setSeen] = useState(() => typeof IntersectionObserver === 'undefined')
  useEffect(() => {
    const el = ref.current
    if (seen || !el) return
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setSeen(true)
          io.disconnect()
        }
      },
      { threshold },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [ref, seen, threshold])
  return seen
}

/** Width in px of an element, kept current with a ResizeObserver. */
export function useElementWidth(ref: RefObject<HTMLElement>, fallback = 560): number {
  const [w, setW] = useState(fallback)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const read = () => {
      const x = Math.round(el.getBoundingClientRect().width)
      if (x > 0) setW(x)
    }
    read()
    if (typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(read)
    ro.observe(el)
    return () => ro.disconnect()
  }, [ref])
  return w
}

/**
 * Interactive-legend state for one chart: the hidden series (kept in `?off=<section>:<series>,...`), the toggle that keeps
 * at least one series on, and the hovered/focused series (`hot`) that the chart highlights while it dims the others.
 */
export function useSeries(ctx: Pick<MatrixCtx, 'sp' | 'updateQP'>, section: SectionId, keys: readonly string[]) {
  const raw = ctx.sp.get('off')
  const off = useMemo(() => {
    const p = parseOff(raw, section)
    return new Set([...p].filter((k) => keys.includes(k)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [raw, section, keys.join('|')])
  const [hotRaw, setHot] = useState<string | null>(null)
  // A hidden series can still be under the pointer right after it was clicked off; it must not dim everything else.
  const hot = hotRaw && !off.has(hotRaw) ? hotRaw : null
  const toggle = useCallback(
    (key: string) =>
      ctx.updateQP('off', (latest) => {
        const current = new Set([...parseOff(latest, section)].filter((k) => keys.includes(k)))
        return writeOff(latest, section, toggleSeries(current, key, keys))
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [section, keys.join('|'), ctx.updateQP],
  )
  return { off, hot, setHot, toggle, on: (k: string) => !off.has(k) }
}

/** A stable per-mount ref counter helper: run `fn` once when `ready` first becomes true. */
export function useOnce(ready: boolean, fn: () => void): void {
  const done = useRef(false)
  useEffect(() => {
    if (ready && !done.current) {
      done.current = true
      fn()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready])
}
