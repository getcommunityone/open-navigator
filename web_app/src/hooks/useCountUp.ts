import { useEffect, useState } from 'react'
import { countUpValue } from '../utils/folioMotion'

/**
 * Text for a KPI numeral. Counts up from 0 to `target` (~900 ms, ease-out) whenever the target changes and always ends on
 * `format(target)` exactly. A missing target shows "—" and never animates; reduced motion shows the final value at once.
 */
export function useCountUp(target: number | null, format: (v: number) => string, reduced: boolean, durationMs = 900): string {
  const [anim, setAnim] = useState<{ target: number | null; t: number }>({ target: null, t: 0 })
  useEffect(() => {
    if (target == null || reduced) return
    let raf = 0
    const start = performance.now()
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs)
      setAnim({ target, t })
      if (t < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, reduced, durationMs])
  if (target == null || !Number.isFinite(target)) return '—'
  if (reduced) return format(target)
  const t = anim.target === target ? anim.t : 0
  return t >= 1 ? format(target) : format(countUpValue(target, t))
}
