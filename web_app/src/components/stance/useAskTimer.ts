import { useEffect, useRef, type RefObject } from 'react'

/**
 * A countdown that only counts while `running` and the tab is visible. Progress (0 to 1) is written to `barRef` as a
 * scaleX transform; `onDone` fires once when the time is up. Changing `resetKey` starts over. A frame gap longer than
 * 250 ms (a hidden tab, a stalled device) adds nothing, so the time never runs out behind the player's back.
 */
export function useAskTimer(opts: {
  running: boolean
  totalMs: number
  resetKey: string
  barRef: RefObject<HTMLElement>
  onDone: () => void
}) {
  const { running, totalMs, resetKey, barRef } = opts
  const done = useRef(opts.onDone)
  done.current = opts.onDone
  const elapsed = useRef(0)
  const fired = useRef(false)

  useEffect(() => {
    elapsed.current = 0
    fired.current = false
    if (barRef.current) barRef.current.style.transform = 'scaleX(0)'
  }, [resetKey, barRef])

  useEffect(() => {
    if (!running || fired.current) return
    let raf = 0
    let last = performance.now()
    const tick = (now: number) => {
      const dt = now - last
      last = now
      if (!document.hidden && dt < 250) elapsed.current += dt
      const p = Math.min(1, elapsed.current / totalMs)
      if (barRef.current) barRef.current.style.transform = `scaleX(${p.toFixed(3)})`
      if (p >= 1) {
        fired.current = true
        done.current()
        return
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [running, totalMs, resetKey, barRef])
}
