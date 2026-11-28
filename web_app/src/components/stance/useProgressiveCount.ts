import { useEffect, useState } from 'react'

/**
 * How many of `total` items to draw now (#1458). A unit-box map is 2,240 to 4,188 `<rect>`s; mounting them in one commit is one
 * long task of seconds on a phone at 4x CPU. The first `step` are drawn at once and the rest follow, `step` per frame, so each
 * commit stays well under 100 ms and the map fills in over a few frames. It only grows: boxes already drawn are never
 * remounted, and a map that gets smaller is clamped. Under reduced motion the cost is the same, so it applies there too.
 */
export function useProgressiveCount(total: number, step = 400): number {
  const [shown, setShown] = useState(step)
  useEffect(() => {
    if (shown >= total) return
    const id = window.requestAnimationFrame(() => setShown((n) => n + step))
    return () => window.cancelAnimationFrame(id)
  }, [shown, total, step])
  return Math.min(shown, total)
}
