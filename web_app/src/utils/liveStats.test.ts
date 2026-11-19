import { describe, expect, it } from 'vitest'
import { formatLiveStat } from './liveStats'

describe('formatLiveStat', () => {
  it('formats a real count with its noun', () => {
    expect(formatLiveStat({ key: 'bills', noun: 'bills' }, { bills: 13456 })).toBe('13,456 bills')
  })

  it('shows nothing, never a stand-in number, when the count is unavailable', () => {
    const spec = { key: 'leaders', noun: 'officials' } as const
    expect(formatLiveStat(spec, undefined)).toBeNull()
    expect(formatLiveStat(spec, null)).toBeNull()
    expect(formatLiveStat(spec, {})).toBeNull()
    expect(formatLiveStat(spec, { leaders: null })).toBeNull()
    expect(formatLiveStat(spec, { leaders: 0 })).toBeNull()
    expect(formatLiveStat(spec, { leaders: Number.NaN })).toBeNull()
  })

  it('reads only the field the spec names', () => {
    expect(formatLiveStat({ key: 'events', noun: 'meetings' }, { bills: 5 })).toBeNull()
  })
})
