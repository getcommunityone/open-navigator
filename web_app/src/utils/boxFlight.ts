/**
 * Cross-page and cross-screen particle box flight math (#1400, inspired by vizjb12).
 *
 * Pure layout & sampling math (DOM capture is isolated in `captureDomBoxes`). Any element marked `[data-box]`
 * (map squares, unit-matrix records, 10x10 waffle cells, outcome box-bars) can lift, fly along curved quadratic
 * Bezier arcs with subtle mid-flight tilt, cross-fade colour/size, and reassemble into the destination page's
 * or screen's `[data-box]` layout.
 */
import { easeOutCubic, mixColor } from './boxMorph'

export const MAX_PARTICLES = 360
/** The most `[data-box]` elements a capture measures (see `captureDomBoxes`). */
export const MAX_MEASURED = 1000
export const FLIGHT_LIFT_SCALE = 1.32

export interface ParticleBox {
  /** Center X in viewport coordinates (px). */
  x: number
  /** Center Y in viewport coordinates (px). */
  y: number
  /** Width (px). */
  w: number
  /** Height (px). */
  h: number
  /** Corner radius (px). */
  rx?: number
  color: string
  opacity?: number
  /** Optional group key (`data-state` or `data-group`) for focus/matching. */
  group?: string
  /** The live element this box was measured from (target captures only): a landing re-reads its rect every frame. */
  el?: Element
}

export type CrossFlightKind = 'carry' | 'spawn' | 'fade' | 'scatter'

export interface CrossFlightPose {
  x: number
  y: number
  w: number
  h: number
  rx: number
  color: string
  opacity: number
}

export interface CrossFlightStep {
  kind: CrossFlightKind
  from: CrossFlightPose
  to: CrossFlightPose
  /** Quadratic Bezier control point (px). */
  cx: number
  cy: number
  /** Peak mid-flight rotation (radians); eases back to 0 at landing. */
  angleMax: number
  delay: number
  duration: number
  lifts: boolean
  /** The live destination element: `retargetPlan` keeps `to` equal to its rect, so the flight lands where the DOM box is. */
  toEl?: Element
}

export interface CrossFlightPlan {
  steps: CrossFlightStep[]
  total: number
  lift: number
}

export interface CrossFlightFrame extends CrossFlightPose {
  angle: number
  lifted: number
}

export interface CrossFlightOptions {
  /** Group key (`state_code` or category) to highlight and fly while others scatter/dissolve. */
  focusGroup?: string | null
  lift?: number
  flight?: number
  stagger?: number
  drift?: number
  maxParticles?: number
  /** Curve bow factor (fraction of distance, capped). */
  arc?: number
}

/** Cross-fade from the canvas to the real DOM boxes once the flight has landed (ms). */
export const LANDING_FADE_MS = 120

/**
 * Motion taken from the owner's vizjb12 matrix: a `transform` transition of 600 ms on cubic-bezier(0.7, 0, 0.2, 1) with a
 * small delay by position (index / total, capped), opacity 240 ms. Straight lines, no tilt, no arc, no overshoot.
 */
export const FLIGHT_DEFAULTS = {
  lift: 0,
  flight: 640,
  stagger: 260,
  drift: 0,
  maxParticles: MAX_PARTICLES,
  arc: 0,
} as const

/** `cubic-bezier(x1, y1, x2, y2)` as a function of progress, the CSS timing-function maths. */
export function cubicBezier(x1: number, y1: number, x2: number, y2: number): (t: number) => number {
  const cx = 3 * x1
  const bx = 3 * (x2 - x1) - cx
  const ax = 1 - cx - bx
  const cy = 3 * y1
  const by = 3 * (y2 - y1) - cy
  const ay = 1 - cy - by
  const X = (u: number) => ((ax * u + bx) * u + cx) * u
  const dX = (u: number) => (3 * ax * u + 2 * bx) * u + cx
  const Y = (u: number) => ((ay * u + by) * u + cy) * u
  return (t) => {
    if (t <= 0) return 0
    if (t >= 1) return 1
    let u = t
    for (let i = 0; i < 8; i++) {
      const err = X(u) - t
      if (Math.abs(err) < 1e-5) return Y(u)
      const d = dX(u)
      if (Math.abs(d) < 1e-6) break
      u -= err / d
    }
    let lo = 0
    let hi = 1
    u = t
    for (let i = 0; i < 24; i++) {
      const x = X(u)
      if (Math.abs(x - t) < 1e-5) break
      if (x < t) lo = u
      else hi = u
      u = (lo + hi) / 2
    }
    return Y(u)
  }
}

/** vizjb12's `--ease-in-out`. */
export const easeFlight = cubicBezier(0.7, 0, 0.2, 1)
/** vizjb12's `--ease-out`, for opacity. */
export const easeFade = cubicBezier(0.2, 0, 0, 1)

const pose = (b: ParticleBox): CrossFlightPose => ({
  x: b.x,
  y: b.y,
  w: Math.max(1, b.w),
  h: Math.max(1, b.h),
  rx: b.rx ?? Math.min(b.w, b.h) * 0.14,
  color: b.color || '#0f766e',
  opacity: b.opacity ?? 1,
})

function centroid(bs: Array<{ x: number; y: number }>): { x: number; y: number } | null {
  if (!bs.length) return null
  return {
    x: bs.reduce((a, b) => a + b.x, 0) / bs.length,
    y: bs.reduce((a, b) => a + b.y, 0) / bs.length,
  }
}

/** Deterministic even downsampling so canvas stays 60fps on dense charts/maps. */
export function sampleBoxes(boxes: ParticleBox[], max = MAX_PARTICLES): ParticleBox[] {
  if (max <= 0) return []
  if (boxes.length <= max) return boxes
  const out: ParticleBox[] = []
  const step = boxes.length / max
  for (let i = 0; i < max; i++) {
    out.push(boxes[Math.min(boxes.length - 1, Math.floor(i * step))]!)
  }
  return out
}

/**
 * Plan a particle flight from `from` boxes to `to` boxes in viewport space.
 * - With `focusGroup`: matching boxes lift & reassemble into `to`, while others scatter outward and fade.
 * - Without `focusGroup`: the whole cloud pairs (same group first, else nearest box) and flies across the stage.
 */
export function planCrossFlight(
  rawFrom: ParticleBox[],
  rawTo: ParticleBox[],
  opts: CrossFlightOptions = {},
): CrossFlightPlan {
  const maxP = opts.maxParticles ?? FLIGHT_DEFAULTS.maxParticles
  const liftMs = opts.lift ?? FLIGHT_DEFAULTS.lift
  const flightMs = opts.flight ?? FLIGHT_DEFAULTS.flight
  const staggerMs = opts.stagger ?? FLIGHT_DEFAULTS.stagger
  const driftPx = opts.drift ?? FLIGHT_DEFAULTS.drift
  const arcRatio = opts.arc ?? FLIGHT_DEFAULTS.arc

  const focus = opts.focusGroup ?? null
  let activeFromRaw: ParticleBox[]
  let scatterRaw: ParticleBox[]
  if (focus) {
    activeFromRaw = rawFrom.filter((b) => b.group === focus)
    scatterRaw = rawFrom.filter((b) => b.group !== focus)
    if (activeFromRaw.length === 0) {
      // Fallback: if no box matched the focus group, fly the full cloud instead of losing everything.
      activeFromRaw = rawFrom
      scatterRaw = []
    }
  } else {
    activeFromRaw = rawFrom
    scatterRaw = []
  }

  const from = sampleBoxes(activeFromRaw, maxP)
  const to = sampleBoxes(rawTo, maxP)
  const others = sampleBoxes(scatterRaw, Math.max(0, maxP - Math.min(from.length, to.length)))

  const lift = from.length > 0 && focus ? liftMs : 0
  const steps: CrossFlightStep[] = []
  const toCenter = centroid(to) ?? centroid(from) ?? { x: 0, y: 0 }
  const fromCenter = centroid(from) ?? toCenter

  // Identity (#1485): a box that stands for the same group keeps its place in the order. Within each group the source and the
  // destination boxes are put in reading order and paired rank to rank, so the group moves as a block, no lines cross, and the
  // same record goes to the same slot every time. What a group lacks on one side is paired by nearest among what is left.
  const readOrder = (arr: ParticleBox[], idxs: number[]): number[] => {
    const row = Math.max(2, median(arr.map((b) => b.h)) * 0.6)
    return [...idxs].sort((a, b) => {
      const ra = Math.round(arr[a]!.y / row)
      const rb = Math.round(arr[b]!.y / row)
      return ra !== rb ? ra - rb : arr[a]!.x - arr[b]!.x
    })
  }
  const byGroup = (arr: ParticleBox[]): Map<string, number[]> => {
    const m = new Map<string, number[]>()
    arr.forEach((b, i) => {
      const k = b.group ?? ''
      const l = m.get(k)
      if (l) l.push(i)
      else m.set(k, [i])
    })
    return m
  }
  const usedFrom = new Set<number>()
  const pairedFrom = new Array<number>(to.length).fill(-1)
  const fromG = byGroup(from)
  const toG = byGroup(to)
  toG.forEach((tIdx, key) => {
    const fIdx = fromG.get(key)
    if (!fIdx) return
    const f = readOrder(from, fIdx)
    const t = readOrder(to, tIdx)
    for (let i = 0; i < Math.min(f.length, t.length); i++) {
      pairedFrom[t[i]!] = f[i]!
      usedFrom.add(f[i]!)
    }
  })
  // Leftovers across groups (a destination group the source never had, e.g. grey cells): nearest unused source box.
  for (let j = 0; j < to.length; j++) {
    if (pairedFrom[j]! >= 0 || usedFrom.size >= from.length) continue
    let best = -1
    let bestD = Infinity
    for (let i = 0; i < from.length; i++) {
      if (usedFrom.has(i)) continue
      const d = (from[i]!.x - to[j]!.x) ** 2 + (from[i]!.y - to[j]!.y) ** 2
      if (d < bestD) {
        bestD = d
        best = i
      }
    }
    if (best >= 0) {
      pairedFrom[j] = best
      usedFrom.add(best)
    }
  }

  // Stagger by position in the destination's reading order (vizjb12: delay = index / total), so a layout fills in like a wave.
  const order = readOrder(to, to.map((_, i) => i))
  const rank = new Array<number>(to.length).fill(0)
  order.forEach((j, r) => (rank[j] = to.length > 1 ? r / (to.length - 1) : 0))

  to.forEach((t, j) => {
    const end = pose(t)
    const delay = lift + rank[j]! * staggerMs
    const carryIdx = pairedFrom[j]!
    if (carryIdx >= 0) {
      steps.push({
        kind: 'carry',
        from: pose(from[carryIdx]!),
        to: end,
        cx: 0,
        cy: 0,
        angleMax: 0,
        delay,
        duration: flightMs,
        lifts: Boolean(focus),
        toEl: t.el,
      })
    } else {
      // More boxes here than there: the extra ones fade in where they belong, a little after the rest have started to move.
      steps.push({
        kind: 'spawn',
        from: { ...end, opacity: 0, w: end.w * 0.6, h: end.h * 0.6 },
        to: end,
        cx: 0,
        cy: 0,
        angleMax: 0,
        delay: delay + flightMs * 0.25,
        duration: flightMs * 0.6,
        lifts: false,
        toEl: t.el,
      })
    }
  })

  // Fewer boxes here than there: the surplus fade out where they stand.
  from.forEach((f, i) => {
    if (usedFrom.has(i)) return
    const start = pose(f)
    steps.push({
      kind: 'fade',
      from: start,
      to: { ...start, opacity: 0 },
      cx: 0,
      cy: 0,
      angleMax: 0,
      delay: lift,
      duration: flightMs * 0.5,
      lifts: false,
    })
  })

  // Boxes outside the focused group (a map drill) step back and dissolve; with `drift` 0 they stay put.
  others.forEach((b, i) => {
    const start = pose(b)
    const dx = b.x - fromCenter.x
    const dy = b.y - fromCenter.y
    const len = Math.hypot(dx, dy) || 1
    const end: CrossFlightPose = {
      ...start,
      x: b.x + (dx / len) * driftPx,
      y: b.y + (dy / len) * driftPx,
      w: start.w * (driftPx > 0 ? 0.75 : 1),
      h: start.h * (driftPx > 0 ? 0.75 : 1),
      opacity: 0,
    }
    steps.push({
      kind: 'scatter',
      from: start,
      to: end,
      cx: (start.x + end.x) / 2,
      cy: (start.y + end.y) / 2,
      angleMax: 0,
      delay: (i % 6) * 14,
      duration: flightMs * 0.6,
      lifts: false,
    })
  })

  void toCenter
  void arcRatio
  const total = steps.reduce((a, s) => Math.max(a, s.delay + s.duration), 0)
  return { steps, total, lift }
}

function median(xs: number[]): number {
  if (!xs.length) return 0
  const s = [...xs].sort((a, b) => a - b)
  return s[Math.floor(s.length / 2)]!
}

/**
 * Re-read every landing box's live rect into its step (#1485). The plan was made from a measure taken a moment earlier; if the
 * screen has moved since (fit zoom, scroll, a font, boxes still arriving), the flight lands on where the DOM box is now, not
 * where it was. Reads only; call it before sampling, never between writes.
 */
export function retargetPlan(plan: CrossFlightPlan): number {
  let moved = 0
  for (const s of plan.steps) {
    const el = s.toEl
    if (!el || !el.isConnected) continue
    const r = el.getBoundingClientRect()
    if (r.width <= 0.5 || r.height <= 0.5) continue
    const x = r.left + r.width / 2
    const y = r.top + r.height / 2
    if (Math.abs(s.to.x - x) > 0.01 || Math.abs(s.to.y - y) > 0.01 || Math.abs(s.to.w - r.width) > 0.01) moved++
    s.to.x = x
    s.to.y = y
    s.to.w = r.width
    s.to.h = r.height
  }
  return moved
}

export function sampleCrossStep(step: CrossFlightStep, ms: number, lift: number): CrossFlightFrame {
  const p = step.duration > 0 ? Math.min(1, Math.max(0, (ms - step.delay) / step.duration)) : ms >= step.delay ? 1 : 0
  if (p >= 1) return { ...step.to, angle: 0, lifted: 0 }
  if (ms <= 0 && !step.lifts) return { ...step.from, angle: 0, lifted: 0 }

  const up = step.lifts && lift > 0 ? easeOutCubic(Math.min(1, Math.max(0, ms / lift))) : 0
  const lifted = up * (1 - p)
  const e = easeFlight(p)
  const scale = 1 + (FLIGHT_LIFT_SCALE - 1) * lifted
  const lerp = (a: number, b: number) => a + (b - a) * e
  // Opacity runs on its own, quicker curve (vizjb12: 240 ms against 600 ms for the move).
  const eo = easeFade(Math.min(1, p / 0.45))
  const opacity = step.from.opacity + (step.to.opacity - step.from.opacity) * eo

  return {
    x: lerp(step.from.x, step.to.x),
    y: lerp(step.from.y, step.to.y),
    w: lerp(step.from.w, step.to.w) * scale,
    h: lerp(step.from.h, step.to.h) * scale,
    rx: lerp(step.from.rx, step.to.rx) * scale,
    color: mixColor(step.from.color, step.to.color, e),
    opacity,
    angle: 0,
    lifted,
  }
}

export function sampleCrossFlight(plan: CrossFlightPlan, ms: number): CrossFlightFrame[] {
  return plan.steps.map((s) => sampleCrossStep(s, ms, plan.lift))
}

function readBoxColor(el: Element): string {
  const cs = getComputedStyle(el)
  // `fill` computes to black on an HTML box (it only means something on SVG): reading it painted every span box black (#1485).
  const fill = el instanceof SVGElement ? cs.fill : ''
  if (fill && fill !== 'none' && fill !== 'transparent' && fill !== 'rgba(0, 0, 0, 0)') return fill
  const attrFill = el instanceof SVGElement ? el.getAttribute('fill') : null
  if (attrFill && attrFill !== 'none' && !attrFill.startsWith('url(') && !attrFill.startsWith('var(')) return attrFill
  const bg = cs.backgroundColor
  if (bg && bg !== 'transparent' && bg !== 'rgba(0, 0, 0, 0)') return bg
  const border = cs.borderColor
  if (border && border !== 'transparent' && border !== 'rgba(0, 0, 0, 0)') return border
  return '#0f766e'
}

/**
 * Snapshot all visible `[data-box]` elements inside `root` (or the viewport) in viewport coordinates.
 */
function boxOf(el: Element, vw: number, vh: number, live = false): ParticleBox | null {
  const r = el.getBoundingClientRect()
  if (r.width <= 0.5 || r.height <= 0.5) return null
  if (r.bottom <= 0 || r.top >= vh || r.right <= 0 || r.left >= vw) return null
  const cs = getComputedStyle(el)
  let op = Number(cs.opacity)
  // A landing box is read for where it will be and in what colour, not how far its own fade-in has got (#1485): a box measured
  // at 40 % opacity would be landed dim and then jump to full.
  if (live) op = 1
  else if (Number.isFinite(op) && op <= 0.01) return null
  const rxAttr = Number(el.getAttribute('rx'))
  const rx = Number.isFinite(rxAttr) && rxAttr > 0 ? rxAttr : Math.min(r.width, r.height) * 0.14
  const group = el.getAttribute('data-state') || el.getAttribute('data-group') || undefined
  return {
    x: r.left + r.width / 2,
    y: r.top + r.height / 2,
    w: r.width,
    h: r.height,
    rx,
    color: readBoxColor(el),
    opacity: Number.isFinite(op) ? op : 1,
    group,
    ...(live ? { el } : {}),
  }
}

export function captureDomBoxes(root?: Element | null, maxMeasured = MAX_MEASURED, live = false): ParticleBox[] {
  if (typeof document === 'undefined' || typeof window === 'undefined') return []
  const scope: ParentNode = root ?? document
  const all = scope.querySelectorAll('[data-box]')
  // A county map draws thousands of boxes and a flight carries at most MAX_PARTICLES: measuring every one (a layout read and a
  // style read each) cost hundreds of ms on a phone per screen change (#1411). An even stride keeps every group represented.
  const stride = all.length > maxMeasured ? all.length / maxMeasured : 1
  const nodes: Element[] = []
  for (let i = 0; i < all.length; i += stride) nodes.push(all[Math.floor(i)]!)
  const vw = window.innerWidth
  const vh = window.innerHeight
  const out: ParticleBox[] = []
  nodes.forEach((el) => {
    const b = boxOf(el, vw, vh, live)
    if (b) out.push(b)
  })
  return out
}

/**
 * Same snapshot as `captureDomBoxes`, taken in slices (default 250 elements, then a macrotask) so a map of thousands of
 * boxes never holds the main thread for one long task (#1416). Resolves with what was read; `isStale()` turning true
 * (the page moved on) abandons it with an empty list.
 */
export async function captureDomBoxesChunked(root?: Element | null, opts: { chunk?: number; isStale?: () => boolean } = {}): Promise<ParticleBox[]> {
  if (typeof document === 'undefined' || typeof window === 'undefined') return []
  const nodes = Array.from((root ?? document).querySelectorAll('[data-box]'))
  const chunk = opts.chunk ?? 250
  const vw = window.innerWidth
  const vh = window.innerHeight
  const out: ParticleBox[] = []
  for (let i = 0; i < nodes.length; i += chunk) {
    if (opts.isStale?.()) return []
    for (const el of nodes.slice(i, i + chunk)) {
      const b = boxOf(el, vw, vh)
      if (b) out.push(b)
    }
    if (i + chunk < nodes.length) await new Promise<void>((r) => window.setTimeout(r, 0))
  }
  return out
}
