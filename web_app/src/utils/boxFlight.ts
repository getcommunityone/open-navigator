/**
 * Cross-page and cross-screen particle box flight math (#1400, inspired by vizjb12).
 *
 * Pure layout & sampling math (DOM capture is isolated in `captureDomBoxes`). Any element marked `[data-box]`
 * (map squares, unit-matrix records, 10x10 waffle cells, outcome box-bars) can lift, fly along curved quadratic
 * Bezier arcs with subtle mid-flight tilt, cross-fade colour/size, and reassemble into the destination page's
 * or screen's `[data-box]` layout.
 */
import { easeOutCubic, easeOutExpo, mixColor } from './boxMorph'

export const MAX_PARTICLES = 360
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

export const FLIGHT_DEFAULTS = {
  lift: 120,
  flight: 580,
  stagger: 220,
  drift: 68,
  maxParticles: MAX_PARTICLES,
  arc: 0.16,
} as const

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

function bezierCtrl(ax: number, ay: number, bx: number, by: number, idx: number, arcRatio: number): { cx: number; cy: number } {
  const dx = bx - ax
  const dy = by - ay
  const dist = Math.hypot(dx, dy)
  if (dist < 4) return { cx: (ax + bx) / 2, cy: (ay + by) / 2 }
  const sign = idx % 2 === 0 ? 1 : -1
  const bow = Math.min(96, dist * arcRatio) * sign
  const nx = -dy / dist
  const ny = dx / dist
  return {
    cx: (ax + bx) / 2 + nx * bow,
    cy: (ay + by) / 2 + ny * bow,
  }
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

  const lift = from.length > 0 ? liftMs : 0
  const steps: CrossFlightStep[] = []
  const toCenter = centroid(to) ?? centroid(from) ?? { x: 0, y: 0 }
  const fromCenter = centroid(from) ?? toCenter

  // Pair each `to` box to its nearest available `from` box (preferring matching `group` when present).
  const usedFrom = new Set<number>()
  const pairedFrom = new Array<number>(to.length).fill(-1)

  const pickBest = (t: ParticleBox, requireUnused: boolean, preferGroup: boolean): number => {
    let best = -1
    let bestScore = Infinity
    for (let i = 0; i < from.length; i++) {
      if (requireUnused && usedFrom.has(i)) continue
      const f = from[i]!
      const dx = f.x - t.x
      const dy = f.y - t.y
      const distSq = dx * dx + dy * dy
      const groupPenalty = preferGroup && t.group && f.group && t.group !== f.group ? 1e8 : 0
      const score = distSq + groupPenalty
      if (score < bestScore) {
        bestScore = score
        best = i
      }
    }
    return best
  }

  // First pass: 1-to-1 carry pairings (each `from` box carries at most one `to` box).
  for (let j = 0; j < to.length; j++) {
    if (usedFrom.size >= from.length) break
    const p = pickBest(to[j]!, true, true)
    if (p >= 0) {
      usedFrom.add(p)
      pairedFrom[j] = p
    }
  }

  // Stagger center-out around destination centroid.
  const dists = to.map((t) => Math.hypot(t.x - toCenter.x, t.y - toCenter.y))
  const maxDist = Math.max(0, ...dists)

  to.forEach((t, j) => {
    const end = pose(t)
    const delay = lift + (maxDist > 0 ? (dists[j]! / maxDist) * staggerMs : 0)
    const carryIdx = pairedFrom[j]!
    if (carryIdx >= 0) {
      const start = pose(from[carryIdx]!)
      const { cx, cy } = bezierCtrl(start.x, start.y, end.x, end.y, j, arcRatio)
      const angleMax = ((j % 2 === 0 ? 1 : -1) * (0.08 + ((j * 7) % 10) * 0.012))
      steps.push({
        kind: 'carry',
        from: start,
        to: end,
        cx,
        cy,
        angleMax,
        delay,
        duration: flightMs,
        lifts: Boolean(focus),
      })
    } else {
      const nearest = pickBest(t, false, false)
      const src = nearest >= 0 ? pose(from[nearest]!) : { ...end, x: fromCenter.x, y: fromCenter.y }
      const spawnFrom: CrossFlightPose = {
        ...src,
        w: Math.min(src.w, end.w) * 0.45,
        h: Math.min(src.h, end.h) * 0.45,
        opacity: 0,
      }
      const { cx, cy } = bezierCtrl(spawnFrom.x, spawnFrom.y, end.x, end.y, j, arcRatio)
      steps.push({
        kind: 'spawn',
        from: spawnFrom,
        to: end,
        cx,
        cy,
        angleMax: 0,
        delay,
        duration: flightMs,
        lifts: false,
      })
    }
  })

  // Surplus `from` boxes fade cleanly toward the destination centroid.
  from.forEach((f, i) => {
    if (usedFrom.has(i)) return
    const start = pose(f)
    const targetX = start.x + (toCenter.x - start.x) * 0.25
    const targetY = start.y + (toCenter.y - start.y) * 0.25
    const end: CrossFlightPose = {
      ...start,
      x: targetX,
      y: targetY,
      w: start.w * 0.35,
      h: start.h * 0.35,
      opacity: 0,
    }
    const { cx, cy } = bezierCtrl(start.x, start.y, end.x, end.y, i, arcRatio * 0.7)
    steps.push({
      kind: 'fade',
      from: start,
      to: end,
      cx,
      cy,
      angleMax: 0,
      delay: lift,
      duration: flightMs * 0.65,
      lifts: Boolean(focus),
    })
  })

  // Unfocused boxes scatter outward from the focused centroid and dissolve.
  others.forEach((b, i) => {
    const start = pose(b)
    const dx = b.x - fromCenter.x
    const dy = b.y - fromCenter.y
    const len = Math.hypot(dx, dy) || 1
    const end: CrossFlightPose = {
      ...start,
      x: b.x + (dx / len) * driftPx,
      y: b.y + (dy / len) * driftPx,
      w: start.w * 0.75,
      h: start.h * 0.75,
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
      duration: flightMs * 0.75,
      lifts: false,
    })
  })

  const total = steps.reduce((a, s) => Math.max(a, s.delay + s.duration), 0)
  return { steps, total, lift }
}

export function sampleCrossStep(step: CrossFlightStep, ms: number, lift: number): CrossFlightFrame {
  const p = step.duration > 0 ? Math.min(1, Math.max(0, (ms - step.delay) / step.duration)) : ms >= step.delay ? 1 : 0
  if (p >= 1) return { ...step.to, angle: 0, lifted: 0 }
  if (ms <= 0 && !step.lifts) return { ...step.from, angle: 0, lifted: 0 }

  const up = step.lifts && lift > 0 ? easeOutCubic(Math.min(1, Math.max(0, ms / lift))) : 0
  const lifted = up * (1 - p)
  const e = step.kind === 'scatter' || step.kind === 'fade' ? easeOutCubic(p) : easeOutExpo(p)
  const scale = 1 + (FLIGHT_LIFT_SCALE - 1) * lifted

  // Quadratic Bezier interpolation: (1-e)^2*P0 + 2(1-e)e*C + e^2*P1
  const inv = 1 - e
  const x = inv * inv * step.from.x + 2 * inv * e * step.cx + e * e * step.to.x
  const y = inv * inv * step.from.y + 2 * inv * e * step.cy + e * e * step.to.y
  const lerp = (a: number, b: number) => a + (b - a) * e

  const opacity =
    step.kind === 'spawn'
      ? step.to.opacity * Math.min(1, p / 0.42)
      : lerp(step.from.opacity, step.to.opacity)

  return {
    x,
    y,
    w: lerp(step.from.w, step.to.w) * scale,
    h: lerp(step.from.h, step.to.h) * scale,
    rx: lerp(step.from.rx, step.to.rx) * scale,
    color: mixColor(step.from.color, step.to.color, easeOutCubic(Math.max(0, (p - 0.3) / 0.7))),
    opacity,
    angle: step.angleMax * Math.sin(Math.PI * p),
    lifted,
  }
}

export function sampleCrossFlight(plan: CrossFlightPlan, ms: number): CrossFlightFrame[] {
  return plan.steps.map((s) => sampleCrossStep(s, ms, plan.lift))
}

function readBoxColor(el: Element): string {
  const cs = getComputedStyle(el)
  const fill = cs.fill
  if (fill && fill !== 'none' && fill !== 'transparent' && fill !== 'rgba(0, 0, 0, 0)') return fill
  const attrFill = el.getAttribute('fill')
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
function boxOf(el: Element, vw: number, vh: number): ParticleBox | null {
  const r = el.getBoundingClientRect()
  if (r.width <= 0.5 || r.height <= 0.5) return null
  if (r.bottom <= 0 || r.top >= vh || r.right <= 0 || r.left >= vw) return null
  const cs = getComputedStyle(el)
  const op = Number(cs.opacity)
  if (Number.isFinite(op) && op <= 0.01) return null
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
  }
}

export function captureDomBoxes(root?: Element | null): ParticleBox[] {
  if (typeof document === 'undefined' || typeof window === 'undefined') return []
  const scope: ParentNode = root ?? document
  const nodes = scope.querySelectorAll('[data-box]')
  const vw = window.innerWidth
  const vh = window.innerHeight
  const out: ParticleBox[] = []
  nodes.forEach((el) => {
    const b = boxOf(el, vw, vh)
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
