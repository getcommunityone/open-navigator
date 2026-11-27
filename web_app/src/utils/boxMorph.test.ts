import { describe, expect, it } from 'vitest'
import { mixColor, parseColor, planDrillMorph, sampleAt, sampleStep, type MorphBox } from './boxMorph'

const box = (x: number, y: number, color = '#000000', r = 2): MorphBox => ({ x, y, r, color, mx: x, my: y })

describe('planDrillMorph', () => {
  it('ends every county box exactly at its real place and colour', () => {
    const from = [box(0, 0, '#ffffff', 6)]
    const to = [box(10, 10, '#ff0000'), box(12, 10, '#00ff00'), box(10, 12, '#0000ff')]
    const plan = planDrillMorph(from, to)
    const end = sampleAt(plan, plan.total)
    to.forEach((t, i) => {
      expect(end[i]).toMatchObject({ x: t.x, y: t.y, r: t.r, color: t.color, opacity: 1 })
    })
  })

  it('starts exactly at the national layout', () => {
    const from = [box(0, 0, '#ffffff', 6), box(40, 0, '#eeeeee', 6)]
    const to = [box(1, 1), box(39, 1)]
    const plan = planDrillMorph(from, to, [box(100, 100, '#123456')])
    const start = sampleAt(plan, 0)
    expect(start[0]).toMatchObject({ x: 0, y: 0, r: 6, color: '#ffffff', opacity: 1 })
    expect(start[1]).toMatchObject({ x: 40, y: 0, r: 6, color: '#eeeeee', opacity: 1 })
    expect(start[2]).toMatchObject({ x: 100, y: 100, color: '#123456', opacity: 1 })
  })

  it('more county boxes than national ones: one child carries each parent, the rest spawn from it', () => {
    const from = [box(0, 0), box(100, 0)]
    const to = [box(1, 0), box(5, 0), box(99, 0), box(95, 0), box(90, 0)]
    const plan = planDrillMorph(from, to)
    const kinds = plan.steps.map((s) => s.kind)
    expect(kinds.filter((k) => k === 'carry')).toHaveLength(2)
    expect(kinds.filter((k) => k === 'spawn')).toHaveLength(3)
    // Spawns start from their nearest parent, clear.
    expect(plan.steps[1]!.from).toMatchObject({ x: 0, y: 0, opacity: 0 })
    expect(plan.steps[4]!.from).toMatchObject({ x: 100, y: 0, opacity: 0 })
    expect(plan.steps).toHaveLength(to.length)
  })

  it('fewer county boxes than national ones: surplus parents fade, nothing is invented', () => {
    const from = [box(0, 0), box(50, 0), box(100, 0)]
    const to = [box(2, 0)]
    const plan = planDrillMorph(from, to)
    expect(plan.steps.filter((s) => s.kind === 'carry')).toHaveLength(1)
    const fades = plan.steps.filter((s) => s.kind === 'fade')
    expect(fades).toHaveLength(2)
    const end = sampleAt(plan, plan.total)
    expect(end.slice(1).every((f) => f.opacity === 0)).toBe(true)
  })

  it('no national box for the state: every county box spawns from the grid centre', () => {
    const to = [box(0, 0), box(10, 0)]
    const plan = planDrillMorph([], to)
    expect(plan.steps.every((s) => s.kind === 'spawn')).toBe(true)
    expect(plan.steps[0]!.from).toMatchObject({ x: 5, y: 0 })
    expect(plan.lift).toBe(0)
  })

  it('other states drift outward from the state and fade', () => {
    const plan = planDrillMorph([box(0, 0)], [box(0, 0)], [box(10, 0), box(-10, 0)], { drift: 20 })
    const [right, left] = plan.steps.filter((s) => s.kind === 'scatter')
    expect(right!.to).toMatchObject({ x: 30, y: 0, opacity: 0 })
    expect(left!.to).toMatchObject({ x: -30, y: 0, opacity: 0 })
  })

  it('staggers centre first and stays within about a second', () => {
    const from = [box(50, 50)]
    const to = [box(50, 50), box(0, 50), box(100, 50), box(50, 0)]
    const plan = planDrillMorph(from, to)
    expect(plan.steps[0]!.delay).toBeLessThan(plan.steps[1]!.delay)
    expect(plan.total).toBeGreaterThanOrEqual(700)
    expect(plan.total).toBeLessThanOrEqual(1100)
  })

  it('reverse playback starts at the county layout and ends at the national one', () => {
    const from = [box(0, 0, '#ffffff', 6)]
    const to = [box(10, 10, '#ff0000'), box(12, 10, '#00ff00')]
    const plan = planDrillMorph(from, to, [box(200, 0, '#111111')])
    const start = sampleAt(plan, 0, true)
    expect(start[0]).toMatchObject({ x: 10, y: 10, color: '#ff0000', opacity: 1 })
    expect(start[2]).toMatchObject({ opacity: 0 })
    const end = sampleAt(plan, plan.total, true)
    expect(end[0]).toMatchObject({ x: 0, y: 0, r: 6, color: '#ffffff', opacity: 1 })
    expect(end[1]!.opacity).toBe(0)
    expect(end[2]).toMatchObject({ x: 200, y: 0, opacity: 1 })
  })

  it('lifts the state boxes before they fly', () => {
    const plan = planDrillMorph([box(0, 0, '#000000', 6)], [box(100, 0)])
    const mid = sampleStep(plan.steps[0]!, plan.lift, plan.lift)
    expect(mid.x).toBe(0)
    expect(mid.r).toBeGreaterThan(6)
    expect(mid.lifted).toBeGreaterThan(0.9)
  })
})

describe('colours', () => {
  it('parses hex and rgb', () => {
    expect(parseColor('#fff')).toEqual([255, 255, 255])
    expect(parseColor('#0f766e')).toEqual([15, 118, 110])
    expect(parseColor('rgb(1, 2, 3)')).toEqual([1, 2, 3])
    expect(parseColor('teal')).toBeNull()
  })

  it('mixes, and switches halfway when a colour cannot be read', () => {
    expect(mixColor('#000000', '#ffffff', 0.5)).toBe('rgb(128, 128, 128)')
    expect(mixColor('#000000', '#ffffff', 1)).toBe('#ffffff')
    expect(mixColor('teal', '#ffffff', 0.4)).toBe('teal')
    expect(mixColor('teal', '#ffffff', 0.6)).toBe('#ffffff')
  })
})
