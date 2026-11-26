import { describe, expect, it } from 'vitest'
import {
  fullRunPhaseFromLog,
  fullRunPhaseLabel,
  stageOwnsFullRunLog,
} from './batchJobFullRunPhase'

describe('fullRunPhaseFromLog', () => {
  it('defaults Run all to Discover before any banner', () => {
    expect(fullRunPhaseFromLog([], '', { step: 'all' })).toBe('discover')
  })

  it('defaults Run each to Videos (no Discover)', () => {
    expect(fullRunPhaseFromLog([], '', { step: 'each' })).toBe('videos')
  })

  it('stays on Discover while channel candidates run', () => {
    const lines = [
      '=== Discover (channel candidates) ===',
      'Discovering YouTube channels for Coffee, AL',
      'Testing 13 common handle patterns...',
    ]
    expect(
      fullRunPhaseFromLog(lines, '--- Discover (channel candidates) ---', {
        step: 'all',
      }),
    ).toBe('discover')
  })

  it('moves to Videos once Catalog banner appears', () => {
    const lines = [
      '=== Discover (channel candidates) ===',
      '=== Catalog → captions → analyze-light → reports-light ===',
      '=== Catalog: max 10 video(s) per channel ===',
      '--- Catalog: AL — Anniston ---',
    ]
    expect(fullRunPhaseFromLog(lines, '--- Catalog: AL — Anniston ---', { step: 'all' })).toBe(
      'videos',
    )
  })
})

describe('stageOwnsFullRunLog', () => {
  it('does not give Videos the Discover log', () => {
    expect(stageOwnsFullRunLog('videos', 'discover')).toBe(false)
    expect(stageOwnsFullRunLog('discover', 'discover')).toBe(true)
  })

  it('gives Videos the shared log only in catalog phase', () => {
    expect(stageOwnsFullRunLog('videos', 'videos')).toBe(true)
    expect(stageOwnsFullRunLog('discover', 'videos')).toBe(false)
  })
})

describe('fullRunPhaseLabel', () => {
  it('labels Discover clearly', () => {
    expect(fullRunPhaseLabel('discover')).toBe('Discover')
  })
})
