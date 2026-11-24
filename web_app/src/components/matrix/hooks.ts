import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState, type RefObject } from 'react'
import { parseOff, toggleSeries, writeOff } from '../../utils/matrixTable'
import type { MatrixCtx, SectionId } from './types'

/** What a section tells its figure: has the section entered view yet, and the section element (for scroll-scrubbed charts). */
export const SectionContext = createContext<{ seen: boolean; el: HTMLElement | null }>({ seen: true, el: null })
export const useSection = () => useContext(SectionContext)

/** True once the element has been at least `threshold` visible. Stays true (each section animates in once). */
export function useInViewOnce(ref: RefObject<Element>, threshold = 0.12, rootMargin?: string): boolean {
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
      { threshold, rootMargin },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [ref, seen, threshold, rootMargin])
  return seen
}

/**
 * When a title plays its entrance: once, when 20% of it is in view above the bottom 10% of the viewport. These are the
 * reference's own numbers (its `[data-reveal]` observer: threshold 0.20, rootMargin 0 0 -10% 0), applied to the title block
 * itself so a very tall section cannot delay it. Stays true afterwards: a filter change never replays it.
 */
export const useTitleShown = (ref: RefObject<Element>): boolean => useInViewOnce(ref, 0.2, '0px 0px -10% 0px')

/**
 * A chart height that fits the window: `preferred`, or what is left of the viewport after `reserve` px of header, story bar,
 * controls and caption (never under `min`). Only on a desktop-width window, where a section is one screen; elsewhere `preferred`.
 */
export function useFitHeight(preferred: number, reserve: number, min = 230): number {
  const calc = () => (typeof window === 'undefined' || window.innerWidth < 1024 ? preferred : Math.round(Math.max(min, Math.min(preferred, window.innerHeight - reserve))))
  const [h, setH] = useState(calc)
  useEffect(() => {
    const on = () => setH(calc())
    on()
    window.addEventListener('resize', on)
    return () => window.removeEventListener('resize', on)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preferred, reserve, min])
  return h
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
