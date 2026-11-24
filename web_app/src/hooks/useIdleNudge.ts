import { useEffect, useRef, type RefObject } from 'react'
import { NUDGE_CYCLE_MS, NUDGE_TICK_MS, arrivalTime, shouldNudge, type NudgeBlocks } from '../utils/idleNudge'

interface Options {
  /** The page (hub, story or challenge). */
  rootRef: RefObject<HTMLElement>
  /** CSS selector of the screen in view inside the root; omitted, the whole root is one screen. */
  screen?: string
  /** Changes when the screen in view changes: the count starts again and the idle clock waits for the entrance. */
  resetKey?: string | number
  /** How long this screen's entrance takes (0 for a page with none). */
  entranceMs?: number
  /** Called when a cue begins; `first` is true for the first cue since the reader last did something. */
  onNudge?: (first: boolean) => void
}

const NUDGE_CLASS = 'is-nudging'
const ACTIONS = 'button, a[href]'

/** What is in the way of a cue right now, read from the page itself so every page gets the same rules. */
function blocksNow(root: HTMLElement, target: HTMLElement | null): NudgeBlocks {
  const ae = document.activeElement as HTMLElement | null
  const typing = Boolean(ae && (ae.tagName === 'INPUT' || ae.tagName === 'TEXTAREA' || ae.tagName === 'SELECT' || ae.isContentEditable))
  const sel = typeof window.getSelection === 'function' ? window.getSelection() : null
  return {
    dialog: document.querySelector('[role="dialog"], dialog[open]') != null,
    table: root.querySelector('[aria-controls^="stance-data-"][aria-expanded="true"]') != null,
    typing,
    selecting: Boolean(sel && !sel.isCollapsed && sel.toString().trim().length > 0),
    hidden: document.hidden,
    noNext: target == null,
  }
}

/**
 * The element to cue. The floating bar when it is showing its one action (the screen's own primary button is then out of
 * view); otherwise that primary button itself. A group of answers is never cued: no answer is pushed.
 */
function findTarget(root: HTMLElement, screen: string | undefined): HTMLElement | null {
  const bar = root.querySelector<HTMLElement>('.stance-float')
  if (bar) return bar.classList.contains('is-many') ? null : bar
  const scope = screen ? root.querySelector<HTMLElement>(screen) : root
  if (!scope) return null
  for (const el of Array.from(scope.querySelectorAll<HTMLElement>('[data-primary]'))) {
    if (el.getClientRects().length > 0) return el.matches(ACTIONS) && !(el as HTMLButtonElement).disabled ? el : null
  }
  return null
}

/**
 * Draws attention to the next step when the reader has stopped (#930). After about six seconds with no scroll, tap or key,
 * the screen's primary action (or the floating bar that stands in for it) gets the class `is-nudging` for one cue; the cue
 * repeats a few times, spaced out, then rests. Any interaction starts over. It is visual only: focus does not move, nothing
 * is announced, no element is added and no layout changes. stance.css draws the cue (calm on the hub and the story, livelier
 * on the challenge, opacity only under reduced motion). Timings: `utils/idleNudge.ts`.
 */
export function useIdleNudge({ rootRef, screen, resetKey, entranceMs = 0, onNudge }: Options): void {
  const cb = useRef(onNudge)
  cb.current = onNudge

  useEffect(() => {
    const root = rootRef.current
    if (!root || typeof window === 'undefined') return
    let last = arrivalTime(performance.now(), entranceMs)
    let lastNudge: number | null = null
    let shown = 0
    let nudged: HTMLElement | null = null
    let off = 0

    const clear = () => {
      window.clearTimeout(off)
      nudged?.classList.remove(NUDGE_CLASS)
      nudged = null
    }
    const touch = () => {
      // An entrance still playing keeps its later start.
      last = Math.max(last, performance.now())
      lastNudge = null
      shown = 0
      clear()
    }
    const tick = () => {
      const now = performance.now()
      const target = findTarget(root, screen)
      if (!shouldNudge({ now, lastInteraction: last, lastNudge, shown, blocked: blocksNow(root, target) }) || !target) return
      clear()
      lastNudge = now
      shown += 1
      nudged = target
      target.classList.add(NUDGE_CLASS)
      off = window.setTimeout(clear, NUDGE_CYCLE_MS)
      cb.current?.(shown === 1)
    }

    const passive = { passive: true, capture: true } as const
    const events = ['scroll', 'wheel', 'touchstart', 'touchmove', 'pointerdown', 'keydown', 'input'] as const
    events.forEach((e) => window.addEventListener(e, touch, passive))
    document.addEventListener('visibilitychange', touch)
    const timer = window.setInterval(tick, NUDGE_TICK_MS)
    return () => {
      window.clearInterval(timer)
      events.forEach((e) => window.removeEventListener(e, touch, { capture: true }))
      document.removeEventListener('visibilitychange', touch)
      clear()
    }
  }, [rootRef, screen, resetKey, entranceMs])
}
