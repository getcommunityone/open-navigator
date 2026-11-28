import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import usePrefersReducedMotion from '../../hooks/usePrefersReducedMotion'
import {
  captureDomBoxes,
  easeOutCubicSafe,
  planCrossFlight,
  sampleCrossFlight,
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
      if (reduced || typeof document === 'undefined') return
      const from = opts.boxes && opts.boxes.length > 0 ? opts.boxes : captureDomBoxes(opts.source ?? null)
      if (!from.length) return
      lastBoxesRef.current = from
      setJob({
        id: seqRef.current++,
        from,
        focusGroup: opts.focusGroup ?? null,
        targetSelector: opts.targetSelector,
      })
    },
    [reduced],
  )

  useEffect(() => {
    if (!job) return
    const canvas = canvasRef.current
    const ctx = canvas?.getContext('2d') ?? null
    if (!canvas || !ctx) {
      clearHiddenMarks()
      setJob(null)
      return
    }

    let dead = false
    let raf = 0
    let plan: CrossFlightPlan | null = null
    let startedAt = 0
    let hiddenTarget: Element | null = null
    let stableCount = 0
    let lastToCount = -1
    const t0 = performance.now()

    const syncSize = () => {
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
    ) => {
      syncSize()
      for (let i = frames.length - 1; i >= 0; i--) {
        const f = frames[i]!
        if (f.opacity <= 0.01 || f.w <= 0.4 || f.h <= 0.4) continue
        ctx.save()
        ctx.translate(f.x, f.y)
        if (f.angle) ctx.rotate(f.angle)
        if (f.lifted && f.lifted > 0.02) {
          ctx.globalAlpha = 0.2 * f.lifted * f.opacity
          ctx.fillStyle = '#1c1917'
          drawRoundedBox(ctx, -f.w / 2 + 1.5, -f.h / 2 + 3.5, f.w * 1.04, f.h * 1.04, f.rx)
        }
        ctx.globalAlpha = Math.min(1, Math.max(0, f.opacity))
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

    const onInterrupt = () => {
      if (performance.now() - t0 < 90) return
      finish()
    }

    const tick = (now: number) => {
      if (dead) return
      if (!plan) {
        if (now - t0 > WAIT_TARGET_MS) {
          finish()
          return
        }
        const target = resolveTarget(job.targetSelector)
        // Poll with a cheap count; read the (possibly thousands of) boxes once, when the target has settled.
        const count = target ? target.querySelectorAll('[data-box]').length : 0
        if (count > 0) {
          if (count === lastToCount) stableCount += 1
          else {
            lastToCount = count
            stableCount = 1
          }
        }
        const to = target && count > 0 && stableCount >= 2 ? captureDomBoxes(target) : []
        if (target && to.length > 0) {
          hiddenTarget = target
          target.setAttribute('data-box-flight-hide', '1')
          plan = planCrossFlight(job.from, to, { focusGroup: job.focusGroup })
          startedAt = job.focusGroup ? now - Math.min(plan.lift, now - t0) : now
        } else {
          // Hold / gently lift the starting boxes while waiting for the next page/screen to render its marks.
          const holdP = easeOutCubicSafe((now - t0) / 140)
          const focus = job.focusGroup
          const hasFocusMatch = Boolean(focus && job.from.some((b) => b.group === focus))
          renderFrames(
            job.from.map((b) => {
              const isFocus = !hasFocusMatch || b.group === focus
              const liftScale = isFocus ? 1 + 0.18 * holdP : 1
              return {
                x: b.x,
                y: b.y - (isFocus ? 4 * holdP : 0),
                w: b.w * liftScale,
                h: b.h * liftScale,
                rx: (b.rx ?? Math.min(b.w, b.h) * 0.14) * liftScale,
                color: b.color,
                opacity: (b.opacity ?? 1) * (isFocus ? 1 : 1 - 0.55 * holdP),
                lifted: isFocus ? holdP : 0,
              }
            }),
          )
          raf = requestAnimationFrame(tick)
          return
        }
      }

      const elapsed = now - startedAt
      if (elapsed >= plan.total) {
        finish()
        return
      }
      renderFrames(sampleCrossFlight(plan, elapsed))
      raf = requestAnimationFrame(tick)
    }

    raf = requestAnimationFrame(tick)
    window.addEventListener('pointerdown', onInterrupt, true)
    window.addEventListener('keydown', onInterrupt, true)

    return () => {
      dead = true
      cancelAnimationFrame(raf)
      if (hiddenTarget) hiddenTarget.removeAttribute('data-box-flight-hide')
      clearHiddenMarks()
      window.removeEventListener('pointerdown', onInterrupt, true)
      window.removeEventListener('keydown', onInterrupt, true)
    }
  }, [job])

  const value = useMemo<BoxFlightApi>(
    () => ({
      launch,
      rememberBoxes,
      getLastBoxes,
      isFlying: job != null,
    }),
    [launch, rememberBoxes, getLastBoxes, job],
  )

  return (
    <BoxFlightContext.Provider value={value}>
      {children}
      {job && <canvas ref={canvasRef} className="box-flight-canvas" aria-hidden="true" />}
    </BoxFlightContext.Provider>
  )
}
