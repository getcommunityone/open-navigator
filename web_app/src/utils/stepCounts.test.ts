import { describe, expect, it } from 'vitest'
import { hasProblems, sumDbtCounts } from './stepCounts'

describe('sumDbtCounts (#843)', () => {
  it('adds the dbt steps of a run together', () => {
    const steps: Array<{ counts: Record<string, number> }> = [
      { counts: { models: 1, success: 1, error: 0, skipped: 0 } },
      { counts: { videos: 10, events: 10 } },
      { counts: { read: 5, loaded: 4, skipped: 1, errors: 0 } },
      { counts: { models: 71, success: 69, error: 2, skipped: 0 } },
    ]
    expect(sumDbtCounts(steps)).toEqual({ models: 72, success: 70, error: 2 })
  })

  it('is null when no dbt step recorded counts', () => {
    expect(sumDbtCounts([{ counts: null }, {}, { counts: { read: 3 } }])).toBeNull()
  })
})

describe('hasProblems', () => {
  it('is true for a dbt step with a failed model', () => {
    expect(hasProblems({ models: 1, success: 0, error: 1 })).toBe(true)
    expect(hasProblems({ models: 1, success: 1, error: 0 })).toBe(false)
  })
})
