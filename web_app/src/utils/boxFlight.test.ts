import { describe, expect, it } from 'vitest'
import {
  MAX_PARTICLES,
  cubicBezier,
  easeFlight,
  retargetPlan,
  planCrossFlight,
  sampleBoxes,
  sampleCrossFlight,
  sampleCrossStep,
  type ParticleBox,
} from './boxFlight'

const pbox = (x: number, y: number, color = '#0f766e', group?: string, w = 10): ParticleBox => ({
  x,
  y,
  w,
  h: w,
  color,
  group,
})

describe('boxFlight (#1400)', () => {
  it('downsamples deterministically when exceeding maxParticles', () => {
    const many = Array.from({ length: 600 }, (_, i) => pbox(i, i))
    const sampled = sampleBoxes(many, MAX_PARTICLES)
    expect(sampled).toHaveLength(MAX_PARTICLES)
    expect(sampled[0]!.x).toBe(0)
    expect(sampled[sampled.length - 1]!.x).toBeGreaterThan(590)
  })

  it('starts at from pose and lands every destination box cleanly with angle=0', () => {
    const from = [pbox(10, 20, '#111111', 'TX', 12), pbox(30, 20, '#222222', 'TX', 12)]
    const to = [pbox(200, 300, '#0f766e', 'A', 8), pbox(220, 300, '#b45309', 'B', 8), pbox(240, 300, '#0f766e', 'A', 8)]
    const plan = planCrossFlight(from, to)
    expect(plan.steps.filter((s) => s.kind === 'carry')).toHaveLength(2)
    expect(plan.steps.filter((s) => s.kind === 'spawn')).toHaveLength(1)

    const start = sampleCrossFlight(plan, 0)
    expect(start).toContainEqual(expect.objectContaining({ x: 10, y: 20, w: 12, color: '#111111', opacity: 1, angle: 0 }))
    expect(start).toContainEqual(expect.objectContaining({ x: 30, y: 20, w: 12, color: '#222222', opacity: 1, angle: 0 }))

    const first = plan.steps[0]!
    const mid = sampleCrossStep(first, plan.lift + first.duration * 0.5, plan.lift)
    expect(mid.x).toBeGreaterThan(first.from.x)
    expect(mid.x).toBeLessThan(first.to.x)
    expect(mid.angle).toBe(0)

    const end = sampleCrossFlight(plan, plan.total)
    to.forEach((dest, i) => {
      expect(end[i]).toMatchObject({ x: dest.x, y: dest.y, w: dest.w, h: dest.h, color: dest.color, opacity: 1, angle: 0, lifted: 0 })
    })
  })

  it('focusGroup lifts and carries matching boxes while scattering others outward', () => {
    const from = [
      pbox(50, 50, '#0f766e', 'TX', 10),
      pbox(150, 50, '#d6d3d1', 'CA', 10),
      pbox(50, 150, '#d6d3d1', 'NY', 10),
    ]
    const to = [pbox(300, 300, '#0f766e', 'c1', 6), pbox(310, 300, '#b45309', 'c2', 6)]
    const plan = planCrossFlight(from, to, { focusGroup: 'TX', drift: 40 })

    const carries = plan.steps.filter((s) => s.kind === 'carry')
    const scatters = plan.steps.filter((s) => s.kind === 'scatter')
    expect(carries).toHaveLength(1)
    expect(carries[0]!.lifts).toBe(true)
    expect(scatters).toHaveLength(2)
    expect(scatters[0]!.to.x).toBeGreaterThan(150)
    expect(scatters[0]!.to.opacity).toBe(0)
  })

  it('fades surplus from boxes when destination has fewer boxes', () => {
    const from = [pbox(0, 0), pbox(40, 0), pbox(80, 0)]
    const to = [pbox(200, 200)]
    const plan = planCrossFlight(from, to)
    expect(plan.steps.filter((s) => s.kind === 'carry')).toHaveLength(1)
    expect(plan.steps.filter((s) => s.kind === 'fade')).toHaveLength(2)
    const end = sampleCrossFlight(plan, plan.total)
    expect(end[0]!.opacity).toBe(1)
    expect(end[1]!.opacity).toBe(0)
    expect(end[2]!.opacity).toBe(0)
  })

  it('keeps identity: boxes of one group pair rank to rank in reading order', () => {
    const from = [pbox(100, 10, '#111', 'A'), pbox(10, 10, '#111', 'A'), pbox(50, 10, '#111', 'B')]
    const to = [pbox(10, 200, '#111', 'A'), pbox(30, 200, '#111', 'A'), pbox(50, 200, '#111', 'B')]
    const plan = planCrossFlight(from, to)
    const carries = plan.steps.filter((s) => s.kind === 'carry')
    expect(carries).toHaveLength(3)
    const a = carries.filter((c) => c.to.y === 200 && c.from.x !== 50).sort((p, q) => p.to.x - q.to.x)
    expect(a[0]!.from.x).toBe(10)
    expect(a[1]!.from.x).toBe(100)
    expect(carries.find((c) => c.to.x === 50)!.from.x).toBe(50)
  })

  it('moves in a straight line with an ease that never overshoots', () => {
    expect(easeFlight(0)).toBe(0)
    expect(easeFlight(1)).toBe(1)
    for (let t = 0; t <= 1.0001; t += 0.01) {
      const e = easeFlight(t)
      expect(e).toBeGreaterThanOrEqual(0)
      expect(e).toBeLessThanOrEqual(1)
    }
    expect(cubicBezier(0, 0, 1, 1)(0.37)).toBeCloseTo(0.37, 3)
    const plan = planCrossFlight([pbox(0, 0)], [pbox(100, 100)])
    const s = plan.steps[0]!
    const mid = sampleCrossStep(s, s.delay + s.duration * 0.3, plan.lift)
    expect(mid.y).toBeCloseTo(mid.x, 6)
    expect(mid.angle).toBe(0)
    expect(plan.total).toBeGreaterThanOrEqual(600)
    expect(plan.total).toBeLessThanOrEqual(950)
  })

  it('extra destination boxes fade in where they land, surplus source boxes fade out where they stand', () => {
    const plan = planCrossFlight([pbox(0, 0)], [pbox(200, 200), pbox(220, 200)])
    const spawn = plan.steps.find((s) => s.kind === 'spawn')!
    expect([spawn.from.x, spawn.from.y]).toEqual([spawn.to.x, spawn.to.y])
    expect(spawn.from.opacity).toBe(0)
    const out = planCrossFlight([pbox(0, 0), pbox(40, 0)], [pbox(200, 200)])
    const fade = out.steps.find((s) => s.kind === 'fade')!
    expect([fade.from.x, fade.from.y]).toEqual([fade.to.x, fade.to.y])
  })

  it('retargetPlan re-reads the live element rect so the flight lands on it', () => {
    const el = { isConnected: true, getBoundingClientRect: () => ({ left: 90, top: 190, width: 20, height: 20 }) } as unknown as Element
    const plan = planCrossFlight([pbox(0, 0)], [{ ...pbox(100, 200, '#0f766e', undefined, 20), el }])
    expect(retargetPlan(plan)).toBe(0)
    ;(el as unknown as { getBoundingClientRect: () => unknown }).getBoundingClientRect = () => ({ left: 90, top: 250, width: 20, height: 20 })
    expect(retargetPlan(plan)).toBe(1)
    expect(sampleCrossFlight(plan, plan.total)[0]).toMatchObject({ x: 100, y: 260, w: 20, h: 20 })
  })
})
