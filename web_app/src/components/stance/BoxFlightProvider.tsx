import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import usePrefersReducedMotion from '../../hooks/usePrefersReducedMotion'
import {
  captureDomBoxes,
  easeOutCubicSafe,
  planCrossFlight,
  retargetPlan,
  sampleCrossFlight,
  LANDING_FADE_MS,
  MAX_MEASURED,
  type CrossFlightPlan,
  type ParticleBox,
} from './boxFlightBridge'

export interface LaunchFlightOptions {
  /** DOM subtree whose `[data-box]` elements start the flight (ignored when `boxes` is given). */
  source?: Element | null
  /** Pre-captured starting boxes in viewport space. */
  boxes?: ParticleBox[]
  /** Group key (`data-state` or `data-group`) to lift & fly while others scatter and dissolve. */
  focusGroup?: string | null
  /** CSS selector for the destination container whose `[data-box]` marks receive the particles. */
  targetSelector: string
}

interface FlightJob {
  id: number
  from: ParticleBox[]
  focusGroup: string | null
  targetSelector: string
  /** Reduced motion: no flight, the target's boxes fade in. */
  reduced: boolean
}

export interface BoxFlightApi {
  /** Start a cross-page or cross-screen particle flight toward `targetSelector`. */
  launch: (opts: LaunchFlightOptions) => void
  /** Save a clean snapshot of visible boxes before a scroll/navigation hides or moves them. */
  rememberBoxes: (boxes: ParticleBox[]) => void
  /** Last remembered snapshot (or empty). */
  getLastBoxes: () => ParticleBox[]
  /** True while a flight is waiting for its target or animating across the viewport. */
  isFlying: boolean
}

const NOOP_API: BoxFlightApi = {
  launch: () => {},
  rememberBoxes: () => {},
  getLastBoxes: () => [],
  isFlying: false,
}

const BoxFlightContext = createContext<BoxFlightApi>(NOOP_API)

export function useBoxFlight(): BoxFlightApi {
  return useContext(BoxFlightContext)
}

const WAIT_TARGET_MS = 2200
/** The target must hold still this long (layout, scroll, fonts) before the flight is planned toward it (#1485). */
const SETTLE_MS = 110
/** A target that never holds still is flown to after this long: the landing then follows the live boxes (retargetPlan). */
const SETTLE_GIVE_UP_MS = 1700
/** Reduced motion: the old boxes are not drawn; the new ones fade in (ms). */
const REDUCED_FADE_MS = 160

/** A cheap fingerprint of a target's layout: box count, a spread of box rects, the scroll position and the font state. */
function layoutSignature(target: Element): string {
  const all = target.querySelectorAll('[data-box]')
  const n = all.length
  const parts: string[] = [String(n), String(Math.round(window.scrollY)), document.fonts?.status ?? '']
  const k = Math.min(n, 28)
  for (let i = 0; i < k; i++) {
    const r = all[k === 1 ? 0 : Math.floor((i * (n - 1)) / (k - 1))]!.getBoundingClientRect()
    parts.push(`${Math.round(r.left * 4)},${Math.round(r.top * 4)},${Math.round(r.width * 4)}`)
  }
  return parts.join('|')
}

/** Test hook: with `window.__boxFlightProbe = true` each flight leaves its final canvas poses for e2e/box-flight-landing. */
interface FlightProbe {
  target: string
  poses: Array<{ x: number; y: number; w: number; h: number; el: Element | null; kind: string }>
  at: number
}
/** A target that exists but has drawn no boxes after this long has none (#1415). */
const TARGET_EMPTY_MS = 500

function drawRoundedBox(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  rx: number,
): void {
  const r = Math.min(rx, w / 2, h / 2)
  if (typeof ctx.roundRect === 'function') {
    ctx.beginPath()
    ctx.roundRect(x, y, w, h, r)
    ctx.fill()
    return
  }
  ctx.fillRect(x, y, w, h)
}

function clearHiddenMarks(): void {
  if (typeof document === 'undefined') return
  document.querySelectorAll('[data-box-flight-hide]').forEach((el) => el.removeAttribute('data-box-flight-hide'))
  document.querySelectorAll('[data-box-flight-prehide]').forEach((el) => el.removeAttribute('data-box-flight-prehide'))
  document.querySelectorAll('[data-box-flight-reveal]').forEach((el) => el.removeAttribute('data-box-flight-reveal'))
}

/** Resolve comma-separated selectors in priority order (unlike `querySelector`, which returns first in DOM order). */
function resolveTarget(selectorList: string): Element | null {
  for (const raw of selectorList.split(',')) {
    const sel = raw.trim()
    if (!sel) continue
    const el = document.querySelector(sel)
    if (el) return el
  }
  return null
}

/**
 * Viewport-level particle stage (#1400): renders flying `[data-box]` squares across route changes (`/` ↔ `/stories/:id`)
 * and across story screens (`useStoryBoxTransition`). Under `prefers-reduced-motion: reduce`, launches are no-ops.
 */
export function BoxFlightProvider({ children }: { children: ReactNode }) {
  const reduced = usePrefersReducedMotion()
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [job, setJob] = useState<FlightJob | null>(null)
  const seqRef = useRef(1)
  const lastBoxesRef = useRef<ParticleBox[]>([])

  const rememberBoxes = useCallback((boxes: ParticleBox[]) => {
    if (boxes.length > 0) lastBoxesRef.current = boxes
  }, [])

  const getLastBoxes = useCallback(() => lastBoxesRef.current, [])

  const launch = useCallback(
    (opts: LaunchFlightOptions) => {
      if (typeof document === 'undefined') return
      const from = opts.boxes && opts.boxes.length > 0 ? opts.boxes : captureDomBoxes(opts.source ?? null)
      if (!from.length) return
      lastBoxesRef.current = from
      setJob({
        id: seqRef.current++,
        from,
        focusGroup: opts.focusGroup ?? null,
        targetSelector: opts.targetSelector,
        reduced,
      })
    },
    [reduced],
  )

  useEffect(() => {
    if (!job) return
    const canvas = canvasRef.current
    const ctx = canvas?.getContext('2d') ?? null
    if (!job.reduced && (!canvas || !ctx)) {
      clearHiddenMarks()
      setJob(null)
      return
    }

    let dead = false
    let raf = 0
    let plan: CrossFlightPlan | null = null
    let startedAt = 0
    let hiddenTarget: Element | null = null
    let sig = ''
    let stableSince = 0
    // After the flight has landed: the canvas fades out while the DOM boxes fade in, on the same rects.
    let fadeAt = 0
    const t0 = performance.now()

    const syncSize = () => {
      if (!canvas || !ctx) return
      const dpr = window.devicePixelRatio || 1
      const w = window.innerWidth
      const h = window.innerHeight
      if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
        canvas.width = Math.round(w * dpr)
        canvas.height = Math.round(h * dpr)
        canvas.style.width = `${w}px`
        canvas.style.height = `${h}px`
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, w, h)
    }

    const renderFrames = (
      frames: Array<{
        x: number
        y: number
        w: number
        h: number
        rx: number
        color: string
        opacity: number
        angle?: number
        lifted?: number
      }>,
      alpha = 1,
    ) => {
      if (!ctx) return
      syncSize()
      for (let i = frames.length - 1; i >= 0; i--) {
        const f = frames[i]!
        const o = f.opacity * alpha
        if (o <= 0.01 || f.w <= 0.4 || f.h <= 0.4) continue
        ctx.save()
        ctx.translate(f.x, f.y)
        if (f.angle) ctx.rotate(f.angle)
        if (f.lifted && f.lifted > 0.02) {
          ctx.globalAlpha = 0.2 * f.lifted * o
          ctx.fillStyle = '#1c1917'
          drawRoundedBox(ctx, -f.w / 2 + 1.5, -f.h / 2 + 3.5, f.w * 1.04, f.h * 1.04, f.rx)
        }
        ctx.globalAlpha = Math.min(1, Math.max(0, o))
        ctx.fillStyle = f.color
        drawRoundedBox(ctx, -f.w / 2, -f.h / 2, f.w, f.h, f.rx)
        ctx.restore()
      }
      ctx.globalAlpha = 1
    }

    const finish = () => {
      if (dead) return
      dead = true
      cancelAnimationFrame(raf)
      if (hiddenTarget) hiddenTarget.removeAttribute('data-box-flight-hide')
      clearHiddenMarks()
      setJob(null)
    }

    /** Hand over to the DOM boxes: they fade 0 -> 1 where the canvas boxes stand (a transition on the reveal attribute). */
    const reveal = (now: number, ms: number) => {
      fadeAt = now
      if (hiddenTarget) {
        hiddenTarget.setAttribute('data-box-flight-reveal', '1')
        ;(hiddenTarget as HTMLElement).style.setProperty('--box-flight-reveal-ms', `${ms}ms`)
        hiddenTarget.removeAttribute('data-box-flight-hide')
      }
    }

    const onInterrupt = () => {
      if (performance.now() - t0 < 90) return
      finish()
    }

    const tick = (now: number) => {
      if (dead) return
      if (fadeAt) {
        const ms = job.reduced ? REDUCED_FADE_MS : LANDING_FADE_MS
        const k = (now - fadeAt) / ms
        if (k >= 1) {
          finish()
          return
        }
        if (plan) {
          retargetPlan(plan)
          renderFrames(sampleCrossFlight(plan, plan.total), 1 - k)
        }
        raf = requestAnimationFrame(tick)
        return
      }
      if (!plan) {
        if (now - t0 > WAIT_TARGET_MS) {
          finish()
          return
        }
        const target = resolveTarget(job.targetSelector)
        const count = target ? target.querySelectorAll('[data-box]').length : 0
        // The target is on screen but has no boxes to land on (a screen of text, a list): there is nothing to fly to, so the
        // held boxes are let go at once, not left drawn over the new screen for the rest of the wait (#1415).
        if (target && count === 0 && now - t0 > TARGET_EMPTY_MS) {
          finish()
          return
        }
        // Settled: the same boxes at the same rects for SETTLE_MS, with the fonts loaded. A target read before this (fit zoom,
        // scroll landing, a late font, boxes still mounting a slice a frame) is what made the canvas land off the DOM (#1485).
        let settled = false
        if (target && count > 0) {
          const s = layoutSignature(target)
          if (s !== sig) {
            sig = s
            stableSince = now
          }
          settled = now - stableSince >= SETTLE_MS && (document.fonts?.status ?? 'loaded') !== 'loading'
          if (!settled && now - t0 > SETTLE_GIVE_UP_MS) settled = true
        }
        const to = settled && target ? captureDomBoxes(target, MAX_MEASURED, true) : []
        if (target && to.length > 0) {
          hiddenTarget = target
          target.setAttribute('data-box-flight-hide', '1')
          if (job.reduced) {
            reveal(now, REDUCED_FADE_MS)
            raf = requestAnimationFrame(tick)
            return
          }
          plan = planCrossFlight(job.from, to, { focusGroup: job.focusGroup })
          startedAt = job.focusGroup ? now - Math.min(plan.lift, now - t0) : now
        } else {
          // Hold the starting boxes (a gentle lift only when one group is in focus) while the next screen settles.
          const holdP = easeOutCubicSafe((now - t0) / 140)
          const focus = job.focusGroup
          const hasFocusMatch = Boolean(focus && job.from.some((b) => b.group === focus))
          renderFrames(
            job.from.map((b) => {
              const isFocus = hasFocusMatch && b.group === focus
              const liftScale = isFocus ? 1 + 0.18 * holdP : 1
              return {
                x: b.x,
                y: b.y - (isFocus ? 4 * holdP : 0),
                w: b.w * liftScale,
                h: b.h * liftScale,
                rx: (b.rx ?? Math.min(b.w, b.h) * 0.14) * liftScale,
                color: b.color,
                opacity: (b.opacity ?? 1) * (focus && hasFocusMatch && !isFocus ? 1 - 0.55 * holdP : 1),
                lifted: isFocus ? holdP : 0,
              }
            }),
          )
          raf = requestAnimationFrame(tick)
          return
        }
      }
      if (!plan) {
        raf = requestAnimationFrame(tick)
        return
      }

      const elapsed = now - startedAt
      // Landing poses follow the live DOM boxes, so whatever moved since the plan was made, the flight ends on them.
      retargetPlan(plan)
      if (elapsed >= plan.total) {
        const probe = (window as unknown as { __boxFlightProbe?: boolean }).__boxFlightProbe
        const final = sampleCrossFlight(plan, plan.total)
        if (probe) {
          const rec: FlightProbe = {
            target: job.targetSelector,
            at: performance.now(),
            poses: final.map((f, i) => ({ x: f.x, y: f.y, w: f.w, h: f.h, el: plan!.steps[i]!.toEl ?? null, kind: plan!.steps[i]!.kind })),
          }
          ;(window as unknown as { __boxFlightLast?: FlightProbe }).__boxFlightLast = rec
        }
        renderFrames(final)
        reveal(now, LANDING_FADE_MS)
        raf = requestAnimationFrame(tick)
        return
      }
      renderFrames(sampleCrossFlight(plan, elapsed))
      raf = requestAnimationFrame(tick)
    }

    raf = requestAnimationFrame(tick)
    window.addEventListener('pointerdown', onInterrupt, true)
    window.addEventListener('keydown', onInterrupt, true)
    window.addEventListener('touchstart', onInterrupt, true)

    return () => {
      dead = true
      cancelAnimationFrame(raf)
      if (hiddenTarget) hiddenTarget.removeAttribute('data-box-flight-hide')
      clearHiddenMarks()
      window.removeEventListener('pointerdown', onInterrupt, true)
      window.removeEventListener('keydown', onInterrupt, true)
      window.removeEventListener('touchstart', onInterrupt, true)
    }
  }, [job])

  // The API never changes identity while a flight starts and ends (#1411): every story panel and map reads it from context, and a
  // new value redrew them all (the county map's thousands of boxes included) twice per screen change. `isFlying` is read on
  // demand from a ref.
  const flyingRef = useRef(false)
  flyingRef.current = job != null
  const value = useMemo<BoxFlightApi>(
    () => ({
      launch,
      rememberBoxes,
      getLastBoxes,
      get isFlying() {
        return flyingRef.current
      },
    }),
    [launch, rememberBoxes, getLastBoxes],
  )

  return (
    <BoxFlightContext.Provider value={value}>
      {children}
      {job && !job.reduced && <canvas ref={canvasRef} className="box-flight-canvas" aria-hidden="true" />}
    </BoxFlightContext.Provider>
  )
}
