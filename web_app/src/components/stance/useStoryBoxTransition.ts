import { useEffect, useRef, type RefObject } from 'react'
import { captureDomBoxes } from '../../utils/boxFlight'
import { useBoxFlight } from './BoxFlightProvider'

/**
 * Connects a story's screen transitions (`active` screen index) to the viewport `BoxFlightProvider` (#1400):
 * - Snapshots `[data-box]` positions on the resting active screen once it settles.
 * - When `active` changes from `prev` to `next`, launches particle flights from `prev`'s boxes into `[data-panel="${next}"]`.
 */
export function useStoryBoxTransition(
  rootRef: RefObject<HTMLElement | null>,
  active: number,
  reduced: boolean,
): void {
  const flight = useBoxFlight()
  const prevActive = useRef<number | null>(null)
  const byScreen = useRef<Map<number, ReturnType<typeof captureDomBoxes>>>(new Map())

  // Keep a fresh snapshot of the active screen's boxes while resting on it.
  useEffect(() => {
    if (reduced) return
    const root = rootRef.current
    if (!root) return
    const snap = () => {
      if (flight.isFlying) return
      const panel = root.querySelector<HTMLElement>(`[data-panel="${active}"]`)
      if (!panel) return
      const boxes = captureDomBoxes(panel)
      if (boxes.length > 0) {
        byScreen.current.set(active, boxes)
        flight.rememberBoxes(boxes)
      }
    }
    // One snapshot, once the screen is quiet and the browser is idle: a flight measures the live boxes itself, this is the
    // fallback for a screen that has none by then (#1411: two measures of every box per Next were a long task each).
    const idle = (window as { requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => number }).requestIdleCallback
    const cancelIdle = (window as { cancelIdleCallback?: (h: number) => void }).cancelIdleCallback
    let h = 0
    const t1 = window.setTimeout(() => {
      if (idle) h = idle(snap, { timeout: 1500 })
      else snap()
    }, 600)
    return () => {
      window.clearTimeout(t1)
      if (h && cancelIdle) cancelIdle(h)
    }
  }, [rootRef, active, reduced, flight])

  // Trigger particle flight when moving between story screens.
  useEffect(() => {
    const prev = prevActive.current
    prevActive.current = active
    if (prev == null || prev === active) return
    const root = rootRef.current
    if (!root) return
    const prevPanel = root.querySelector<HTMLElement>(`[data-panel="${prev}"]`)
    const livePrev = prevPanel ? captureDomBoxes(prevPanel) : []
    const fromBoxes = livePrev.length > 0 ? livePrev : (byScreen.current.get(prev) ?? flight.getLastBoxes())
    if (!fromBoxes.length) return
    flight.launch({
      boxes: fromBoxes,
      targetSelector: `.stance-story [data-panel="${active}"]`,
    })
  }, [rootRef, active, reduced, flight])
}
