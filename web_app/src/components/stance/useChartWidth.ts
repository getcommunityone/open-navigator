import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * The width of a chart's host element, kept current with a ResizeObserver (the reference's layout-on-resize).
 * `ref` is a callback ref, so a host that mounts later (after a loading state) is still measured.
 */
export function useChartWidth<T extends HTMLElement>(fallback = 540) {
  const [el, setEl] = useState<T | null>(null)
  const [width, setWidth] = useState(fallback)
  const ref = useCallback((node: T | null) => setEl(node), [])
  const frame = useRef(0)
  useEffect(() => {
    if (!el) return
    const read = () => setWidth(Math.round(el.clientWidth || fallback))
    read()
    if (typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(() => {
      cancelAnimationFrame(frame.current)
      frame.current = requestAnimationFrame(read)
    })
    ro.observe(el)
    return () => {
      ro.disconnect()
      cancelAnimationFrame(frame.current)
    }
  }, [el, fallback])
  return { ref, width }
}
