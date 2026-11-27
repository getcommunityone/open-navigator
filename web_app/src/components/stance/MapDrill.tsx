import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useLocation, useNavigate } from 'react-router-dom'
import { COUNTIES_ALBERS_TOPO, NATIONAL_BBOX, STATES_ALBERS_TOPO, fetchTopo } from '../../lib/dotMatrix'
import { STATE_FIPS_TO_CODE } from '../../utils/stateFips'
import usePrefersReducedMotion from '../../hooks/usePrefersReducedMotion'
import { LIFT_SCALE, MORPH_DEFAULTS, easeOutCubic, planDrillMorph, sampleAt, type MorphBox, type MorphPlan } from '../../utils/boxMorph'
import type { StateCount } from './StoryDotMap'
import { NATIONAL_PAD, nationalGrid, nationalPaint } from './nationalDots'
import { DRILL_FROM_NATIONAL } from './drillState'


type Dir = 'in' | 'out'
interface Frame {
  left: number
  top: number
  width: number
  vb: [number, number, number, number]
}
interface Job {
  id: number
  dir: Dir
  stateCode: string
  /** The national map's frame when the reader picked the state (in place). */
  national?: Frame | null
  /** The county boxes as they stood when the reader broadened (out). */
  county?: MorphBox[] | null
}

interface Props {
  /** The state the story is scoped to (null: the whole country). */
  stateCode: string | null
  /** Real meetings per state, nationally (the national map's own counts). */
  byState: StateCount[] | null | undefined
  /** Whether the state's county map will show: still loading, ready, or not at all (no places on record). */
  county: 'loading' | 'ready' | 'none'
  /** The map; call `beforePick(code)` just before narrowing or broadening, so the transition can read where the boxes stand. */
  children: (beforePick: (stateCode: string | null) => void) => ReactNode
}

/** How long the transition waits for the county map's data and shapes before giving up and showing the map as is. */
const WAIT_MS = 10000
const vbOf = (svg: SVGSVGElement): [number, number, number, number] => {
  const v = (svg.getAttribute('viewBox') ?? '').split(/\s+/).map(Number)
  return v.length === 4 && v.every(Number.isFinite) ? (v as [number, number, number, number]) : [0, 0, 1, 1]
}
const frameOf = (wrap: HTMLElement, svg: SVGSVGElement): Frame => {
  const w = wrap.getBoundingClientRect()
  const r = svg.getBoundingClientRect()
  return { left: r.left - w.left, top: r.top - w.top, width: r.width, vb: vbOf(svg) }
}
const svgIn = (wrap: HTMLElement, map: 'national' | 'county') => wrap.querySelector<SVGSVGElement>(`svg.stance-map-svg[data-map="${map}"]`)

/** The county map's boxes as drawn: place, size, colour and opacity on screen, and their map coordinates for pairing. */
function readCounty(wrap: HTMLElement): MorphBox[] | null {
  const svg = svgIn(wrap, 'county')
  if (!svg) return null
  const w = wrap.getBoundingClientRect()
  const m = svg.getScreenCTM()
  if (!m) return null
  const out: MorphBox[] = []
  svg.querySelectorAll<SVGCircleElement>('circle[data-box]').forEach((c) => {
    const cx = Number(c.getAttribute('cx'))
    const cy = Number(c.getAttribute('cy'))
    out.push({
      x: m.a * cx + m.c * cy + m.e - w.left,
      y: m.b * cx + m.d * cy + m.f - w.top,
      r: Number(c.getAttribute('r')) * m.a,
      color: c.getAttribute('fill') ?? '#000',
      opacity: Number(c.getAttribute('opacity') ?? 1),
      mx: cx,
      my: cy,
    })
  })
  return out.length ? out : null
}

/**
 * The state drill-down's transition (#1195): picking a state on the Overview's national box map, the state's boxes lift, fly
 * and re-form into its county box map while the other states' boxes fade and drift away; broadening back plays it backwards.
 * It is drawn on a canvas over the map for its second, then the real map shows again: every box it draws is one of the real
 * maps' boxes (their places and colours are read from the maps themselves), so it only moves boxes that are there.
 *
 * It never moves focus or announces anything; the map underneath stays in the page, with its keyboard navigation and data
 * table. With reduced motion asked for it does nothing. A click or key press during it jumps to the end.
 */
export default function MapDrill({ stateCode, byState, county, children }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const reduced = usePrefersReducedMotion()
  const location = useLocation()
  const navigate = useNavigate()
  const arrival = useRef((location.state as { drillFrom?: string } | null)?.drillFrom === DRILL_FROM_NATIONAL.drillFrom)
  const where = useRef(location)
  where.current = location

  const { data: topo } = useQuery({
    queryKey: ['us-atlas-states-albers'],
    queryFn: () => fetchTopo(STATES_ALBERS_TOPO),
    staleTime: 1000 * 60 * 60,
  })
  const grid = useMemo(() => (topo ? nationalGrid(topo) : null), [topo])
  const live = useRef({ grid, byState, county })
  live.current = { grid, byState, county }

  const [job, setJob] = useState<Job | null>(null)
  const nextId = useRef(1)
  // What the reader's pick saw, used only by the scope change that follows it right away (not a later one from elsewhere).
  const pending = useRef<(Pick<Job, 'national' | 'county'> & { at: number }) | null>(null)
  const prevState = useRef<string | null | undefined>(undefined)

  // The arrival flag is used once: cleared from the history entry so a refresh or Back doesn't replay it.
  const clearArrival = useCallback(() => {
    if (!arrival.current) return
    arrival.current = false
    const l = where.current
    navigate({ pathname: l.pathname, search: l.search, hash: l.hash }, { replace: true, state: null })
  }, [navigate])
  // Read through a ref, so a new navigate identity never restarts a running transition.
  const clearRef = useRef(clearArrival)
  clearRef.current = clearArrival

  // The county shapes are fetched once the reader reaches for the national map, so the county map can draw as soon as its
  // counts arrive and the national map isn't replaced by a loading line meanwhile.
  const queryClient = useQueryClient()
  const prefetchCounties = useCallback(() => {
    void queryClient.prefetchQuery({ queryKey: ['us-atlas-counties-albers'], queryFn: () => fetchTopo(COUNTIES_ALBERS_TOPO), staleTime: 1000 * 60 * 60 })
  }, [queryClient])
  useEffect(() => {
    const wrap = wrapRef.current
    if (!wrap || stateCode || reduced) return
    wrap.addEventListener('pointerenter', prefetchCounties)
    wrap.addEventListener('focusin', prefetchCounties)
    return () => {
      wrap.removeEventListener('pointerenter', prefetchCounties)
      wrap.removeEventListener('focusin', prefetchCounties)
    }
  }, [stateCode, reduced, prefetchCounties])

  const beforePick = useCallback((code: string | null) => {
    const wrap = wrapRef.current
    const cur = prevState.current ?? null
    pending.current = null
    if (!wrap || reduced) return
    if (!cur && code) {
      const svg = svgIn(wrap, 'national')
      pending.current = { national: svg ? frameOf(wrap, svg) : null, at: performance.now() }
    } else if (cur && !code) {
      pending.current = { county: readCounty(wrap), at: performance.now() }
    }
  }, [reduced])

  // Decide when the scope changes: in from the country, or back out to it.
  useEffect(() => {
    const prev = prevState.current
    if (prev === stateCode) return
    prevState.current = stateCode
    const fresh = pending.current && performance.now() - pending.current.at < 2000 ? pending.current : null
    pending.current = null
    const snap = fresh ? { national: fresh.national, county: fresh.county } : null
    let dir: Dir | null = null
    if (prev === undefined) dir = stateCode && arrival.current ? 'in' : null
    else if (!prev && stateCode) dir = 'in'
    else if (prev && !stateCode && snap?.county) dir = 'out'
    if (!dir || reduced) {
      setJob(null)
      if (prev === undefined || reduced) clearRef.current()
      return
    }
    setJob({ id: nextId.current++, dir, stateCode: (stateCode ?? prev)!, ...snap })
  }, [stateCode, reduced])

  // Run the transition.
  useEffect(() => {
    if (!job) return
    const wrap = wrapRef.current
    const canvas = canvasRef.current
    const ctx = canvas?.getContext('2d') ?? null
    if (!wrap || !canvas || !ctx) {
      setJob(null)
      return
    }
    let raf = 0
    let dead = false
    let plan: MorphPlan | null = null
    let startedAt = 0
    let lastNational: Frame | null = job.national ?? null
    const t0 = performance.now()
    const stateFips = Object.entries(STATE_FIPS_TO_CODE).find(([, c]) => c === job.stateCode)?.[0] ?? null
    const finish = () => {
      if (dead) return
      dead = true
      cancelAnimationFrame(raf)
      setJob(null)
      clearRef.current()
    }

    // The canvas covers the boxes only (not the counts and charts under the map), and only ever grows during a run.
    let canvasH = 0
    const size = (h: number) => {
      const dpr = window.devicePixelRatio || 1
      const w = wrap.clientWidth
      canvasH = Math.max(canvasH, Math.ceil(h))
      const hh = canvasH
      if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(hh * dpr)) {
        canvas.width = Math.round(w * dpr)
        canvas.height = Math.round(hh * dpr)
        canvas.style.width = `${w}px`
        canvas.style.height = `${hh}px`
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, w, hh)
    }
    const draw = (frames: { x: number; y: number; r: number; color: string; opacity: number; lifted?: number }[]) => {
      size(frames.reduce((a, f) => Math.max(a, f.y + f.r + 2), 0))
      // Back to front: the other states first, the state's own boxes on top.
      for (let i = frames.length - 1; i >= 0; i--) {
        const f = frames[i]!
        if (f.opacity <= 0.01 || f.r <= 0.05) continue
        if (f.lifted && f.lifted > 0.02) {
          ctx.globalAlpha = 0.22 * f.lifted * f.opacity
          ctx.fillStyle = '#1c1917'
          ctx.beginPath()
          ctx.arc(f.x + f.r * 0.15, f.y + f.r * 0.45, f.r * 1.12, 0, Math.PI * 2)
          ctx.fill()
        }
        ctx.globalAlpha = f.opacity
        ctx.fillStyle = f.color
        ctx.beginPath()
        ctx.arc(f.x, f.y, f.r, 0, Math.PI * 2)
        ctx.fill()
      }
      ctx.globalAlpha = 1
    }

    // The national boxes on screen, split into the state's own and the rest, in a frame's coordinates.
    const nationalBoxes = (fr: Frame) => {
      const g = live.current.grid
      if (!g) return null
      const paint = nationalPaint(live.current.byState)
      const s = fr.width / fr.vb[2]
      const r = g.step * 0.38 * s
      const mine: MorphBox[] = []
      const rest: MorphBox[] = []
      for (const d of g.dots) {
        const p = paint(d.id)
        const b = { x: fr.left + (d.x - fr.vb[0]) * s, y: fr.top + (d.y - fr.vb[1]) * s, r: r * p.rScale, color: p.color, mx: d.x, my: d.y }
        ;(d.id === stateFips ? mine : rest).push(b)
      }
      return { mine, rest }
    }
    const nationalVb: [number, number, number, number] = [-NATIONAL_PAD, -NATIONAL_PAD, NATIONAL_BBOX[2] + NATIONAL_PAD * 2, NATIONAL_BBOX[3] + NATIONAL_PAD * 2]

    const tick = (now: number) => {
      if (dead) return
      if (!plan) {
        // Waiting for the destination map to draw (its data or shapes may still be loading).
        if (now - t0 > WAIT_MS || (job.dir === 'in' && live.current.county === 'none')) return finish()
        const nat = svgIn(wrap, 'national')
        if (nat) lastNational = frameOf(wrap, nat)
        else size(0)
        if (job.dir === 'in') {
          const countySvg = live.current.county === 'ready' ? svgIn(wrap, 'county') : null
          const to = countySvg ? readCounty(wrap) : null
          if (to && countySvg) {
            // Arriving from the home page there was no national map here: lay it out over the county map's width.
            const cf = frameOf(wrap, countySvg)
            const fr = lastNational ?? { left: cf.left, top: cf.top, width: cf.width, vb: nationalVb }
            const nb = nationalBoxes(fr)
            if (!nb) return finish()
            plan = planDrillMorph(nb.mine, to, nb.rest, { drift: Math.min(80, fr.width * 0.08) })
            // The lift may already have played while the county map loaded.
            startedAt = lastNational ? now - Math.min(plan.lift, now - t0) : now
          } else if (nat && lastNational) {
            const nb = nationalBoxes(lastNational)
            // While the county map loads, the state's boxes lift and wait.
            const up = easeOutCubic((now - t0) / MORPH_DEFAULTS.lift)
            if (nb) draw([...nb.mine.map((b) => ({ ...b, r: b.r * (1 + (LIFT_SCALE - 1) * up), opacity: 1, lifted: up })), ...nb.rest.map((b) => ({ ...b, opacity: 1 }))])
          }
        } else {
          const from = job.county ?? null
          if (!from) return finish()
          if (nat && live.current.grid) {
            const nb = nationalBoxes(frameOf(wrap, nat))
            if (!nb) return finish()
            plan = planDrillMorph(nb.mine, from, nb.rest, { drift: Math.min(80, frameOf(wrap, nat).width * 0.08) })
            startedAt = now
          } else {
            draw(from.map((b) => ({ ...b, opacity: b.opacity ?? 1 })))
          }
        }
        if (!plan) {
          raf = requestAnimationFrame(tick)
          return
        }
      }
      const ms = now - startedAt
      if (ms >= plan.total) return finish()
      draw(sampleAt(plan, ms, job.dir === 'out'))
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)

    // A click or key press during the transition jumps to the end: the real map is already there underneath.
    wrap.addEventListener('pointerdown', finish, true)
    wrap.addEventListener('keydown', finish, true)
    return () => {
      dead = true
      cancelAnimationFrame(raf)
      wrap.removeEventListener('pointerdown', finish, true)
      wrap.removeEventListener('keydown', finish, true)
    }
  }, [job])

  return (
    <div ref={wrapRef} className={`stance-map-morph${job ? ' is-morphing' : ''}`}>
      {children(beforePick)}
      {job && <canvas ref={canvasRef} className="stance-map-morph-canvas" aria-hidden="true" />}
    </div>
  )
}
