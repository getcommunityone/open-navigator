/**
 * The state drill-down's "boxes reorganize" transition (#1195), as pure layout math: no DOM, no timers.
 *
 * The national map shows a state as a few big boxes; its county map shows the same state as many small ones. Going in, the
 * state's national boxes lift, then fly and re-form into the county grid; the other states' boxes fade and drift outward.
 * Coming back out plays the same plan backwards. Every box keeps standing for what it stands for: each final box is one of
 * the county map's real boxes, at its real place and colour, and the plan only says where it starts and when it moves.
 *
 * When the two grids hold different numbers of boxes, each county box's parent is the national box nearest it on the map
 * (both grids share the Albers coordinates of us-atlas, given as `mx`/`my`). One child per parent carries the parent's box;
 * the rest spawn from the parent, small and clear, and grow in. A parent with no child fades where it stands.
 */

export interface MorphBox {
  /** Position and radius on screen (px, in the overlay's frame). */
  x: number
  y: number
  r: number
  color: string
  opacity?: number
  /** Map coordinates used to pair boxes across the two grids (defaults to x/y). */
  mx?: number
  my?: number
}

export type MorphKind = 'carry' | 'spawn' | 'fade' | 'scatter'

export interface MorphPose {
  x: number
  y: number
  r: number
  color: string
  opacity: number
}

export interface MorphStep {
  kind: MorphKind
  from: MorphPose
  to: MorphPose
  /** When this box starts to move (ms from the start). */
  delay: number
  /** How long it moves (ms). */
  duration: number
  /** Whether it lifts (scales up with a shadow) before it moves: the selected state's own national boxes. */
  lifts: boolean
}

export interface MorphPlan {
  steps: MorphStep[]
  /** The whole transition's length (ms): every step has landed by then. */
  total: number
  lift: number
}

export interface MorphOptions {
  /** The lift beat before the boxes fly (ms). */
  lift?: number
  /** Each box's flight (ms). */
  flight?: number
  /** The spread of start times, centre first (ms). */
  stagger?: number
  /** How far the other states' boxes drift outward as they fade (px). */
  drift?: number
}

export const MORPH_DEFAULTS: Required<MorphOptions> = { lift: 160, flight: 620, stagger: 260, drift: 60 }
/** How much a lifting box grows. */
export const LIFT_SCALE = 1.3

const pose = (b: MorphBox): MorphPose => ({ x: b.x, y: b.y, r: b.r, color: b.color, opacity: b.opacity ?? 1 })
const mxOf = (b: MorphBox) => b.mx ?? b.x
const myOf = (b: MorphBox) => b.my ?? b.y

function centroid(bs: { x: number; y: number }[]): { x: number; y: number } | null {
  if (!bs.length) return null
  return { x: bs.reduce((a, b) => a + b.x, 0) / bs.length, y: bs.reduce((a, b) => a + b.y, 0) / bs.length }
}

/**
 * Plan national → state. `stateFrom` are the selected state's national boxes, `to` the county map's boxes, `others` every
 * other state's national boxes. Returns one step per `to` box (in `to` order, first), then one per unmatched parent, then one
 * per other box.
 */
export function planDrillMorph(stateFrom: MorphBox[], to: MorphBox[], others: MorphBox[] = [], options: MorphOptions = {}): MorphPlan {
  const o = { ...MORPH_DEFAULTS, ...options }
  const lift = stateFrom.length ? o.lift : 0
  const steps: MorphStep[] = []

  // Each county box's parent: the nearest national box on the map.
  const parentOf = to.map((t) => {
    let best = -1
    let bestD = Infinity
    for (let i = 0; i < stateFrom.length; i++) {
      const dx = mxOf(stateFrom[i]!) - mxOf(t)
      const dy = myOf(stateFrom[i]!) - myOf(t)
      const d = dx * dx + dy * dy
      if (d < bestD) {
        bestD = d
        best = i
      }
    }
    return best
  })
  // The child nearest each parent carries it; the others spawn.
  const carrier = new Map<number, number>()
  const carrierD = new Map<number, number>()
  to.forEach((t, j) => {
    const p = parentOf[j]!
    if (p < 0) return
    const dx = mxOf(stateFrom[p]!) - mxOf(t)
    const dy = myOf(stateFrom[p]!) - myOf(t)
    const d = dx * dx + dy * dy
    if (d < (carrierD.get(p) ?? Infinity)) {
      carrierD.set(p, d)
      carrier.set(p, j)
    }
  })

  // Centre first: a box's start is staggered by its landing spot's distance from the county grid's centre.
  const c = centroid(to)
  const dist = to.map((t) => (c ? Math.hypot(t.x - c.x, t.y - c.y) : 0))
  const maxDist = Math.max(0, ...dist)
  const stateC = centroid(stateFrom) ?? c ?? { x: 0, y: 0 }

  to.forEach((t, j) => {
    const end = pose(t)
    const p = parentOf[j]!
    const delay = lift + (maxDist > 0 ? (dist[j]! / maxDist) * o.stagger : 0)
    if (p >= 0 && carrier.get(p) === j) {
      steps.push({ kind: 'carry', from: pose(stateFrom[p]!), to: end, delay, duration: o.flight, lifts: true })
    } else {
      // Spawned from its parent, or from the state's centre when the state had no national box at all.
      const src = p >= 0 ? stateFrom[p]! : { x: stateC.x, y: stateC.y, r: t.r, color: t.color }
      steps.push({
        kind: 'spawn',
        from: { x: src.x, y: src.y, r: Math.min(src.r, t.r) * 0.5, color: src.color, opacity: 0 },
        to: end,
        delay,
        duration: o.flight,
        lifts: false,
      })
    }
  })
  // Parents with no child fade where they stand.
  stateFrom.forEach((b, i) => {
    if (carrier.has(i)) return
    const from = pose(b)
    steps.push({ kind: 'fade', from, to: { ...from, r: from.r * 0.5, opacity: 0 }, delay: lift, duration: o.flight * 0.6, lifts: true })
  })
  // Every other state's boxes fade as they drift away from the selected state.
  for (const b of others) {
    const from = pose(b)
    const dx = b.x - stateC.x
    const dy = b.y - stateC.y
    const len = Math.hypot(dx, dy) || 1
    steps.push({
      kind: 'scatter',
      from,
      to: { ...from, x: b.x + (dx / len) * o.drift, y: b.y + (dy / len) * o.drift, opacity: 0 },
      delay: 0,
      duration: o.flight * 0.8,
      lifts: false,
    })
  }
  const total = steps.reduce((a, s) => Math.max(a, s.delay + s.duration), 0)
  return { steps, total, lift }
}

export const easeOutExpo = (t: number): number => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t))
export const easeOutCubic = (t: number): number => 1 - Math.pow(1 - Math.min(1, Math.max(0, t)), 3)

/** A colour as [r, g, b], from #rgb, #rrggbb or rgb()/rgba(); null when it can't be read. */
export function parseColor(c: string): [number, number, number] | null {
  const s = c.trim().toLowerCase()
  let m = /^#([0-9a-f])([0-9a-f])([0-9a-f])$/.exec(s)
  if (m) return [parseInt(m[1]! + m[1]!, 16), parseInt(m[2]! + m[2]!, 16), parseInt(m[3]! + m[3]!, 16)]
  m = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/.exec(s)
  if (m) return [parseInt(m[1]!, 16), parseInt(m[2]!, 16), parseInt(m[3]!, 16)]
  m = /^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)/.exec(s)
  if (m) return [Number(m[1]), Number(m[2]), Number(m[3])]
  return null
}

/** The colour `t` of the way from `a` to `b`; when either can't be read, `a` until halfway, then `b`. */
export function mixColor(a: string, b: string, t: number): string {
  if (t <= 0) return a
  if (t >= 1) return b
  const ca = parseColor(a)
  const cb = parseColor(b)
  if (!ca || !cb) return t < 0.5 ? a : b
  const ch = (i: number) => Math.round(ca[i]! + (cb[i]! - ca[i]!) * t)
  return `rgb(${ch(0)}, ${ch(1)}, ${ch(2)})`
}

export interface MorphFrame extends MorphPose {
  /** 0..1: how lifted the box is (its shadow's strength). */
  lifted: number
}

/** Where one box is at `ms` into the plan. At 0 it is exactly `from`; once `delay + duration` has passed, exactly `to`. */
export function sampleStep(step: MorphStep, ms: number, lift: number): MorphFrame {
  const p = step.duration > 0 ? Math.min(1, Math.max(0, (ms - step.delay) / step.duration)) : ms >= step.delay ? 1 : 0
  if (p >= 1) return { ...step.to, lifted: 0 }
  // The lift beat: up to LIFT_SCALE before the flight, eased back down as it lands.
  const up = step.lifts && lift > 0 ? easeOutCubic(ms / lift) : 0
  const lifted = up * (1 - p)
  const e = step.kind === 'scatter' || step.kind === 'fade' ? easeOutCubic(p) : easeOutExpo(p)
  const scale = 1 + (LIFT_SCALE - 1) * lifted
  const lerp = (a: number, b: number) => a + (b - a) * e
  // Spawned boxes are clear at first and grow in over the first part of their flight.
  const opacity = step.kind === 'spawn' ? step.to.opacity * Math.min(1, p / 0.4) : lerp(step.from.opacity, step.to.opacity)
  return {
    x: lerp(step.from.x, step.to.x),
    y: lerp(step.from.y, step.to.y),
    r: lerp(step.from.r, step.to.r) * scale,
    // Colours cross-fade as the box lands.
    color: mixColor(step.from.color, step.to.color, easeOutCubic(Math.max(0, (p - 0.35) / 0.65))),
    opacity,
    lifted,
  }
}

/** The plan at `ms`, forwards (in) or backwards (out: the state's boxes gather back and the country returns). */
export function sampleAt(plan: MorphPlan, ms: number, reverse = false): MorphFrame[] {
  const t = reverse ? plan.total - ms : ms
  return plan.steps.map((s) => sampleStep(s, t, plan.lift))
}
