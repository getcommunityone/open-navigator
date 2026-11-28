import { describe, expect, it } from 'vitest'
import {
  MAX_PARTICLES,
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
    expect(Math.abs(mid.angle)).toBeGreaterThan(0)

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
})
