import { describe, expect, it } from 'vitest'
import type { TrendTerm } from '../api/trendingTerms'
import { chipAriaLabel, clockLabel, momentUrl, parseTrendSort, riseLabel, trendScopeLabel } from './trendingTerms'

// Test-only row: nothing here is served by the app.
const t: TrendTerm = {
  term_id: 'a'.repeat(32),
  term: 'sample term',
  rank: 1,
  meetings_a: 10,
  meetings_b: 40,
  recorded_a: 1000,
  recorded_b: 2000,
  share_a: 0.01,
  share_b: 0.02,
  rise: 2,
  n_meetings: 50,
  n_jurisdictions: 12,
  hot_score: null,
  is_sensitive: false,
  latest_meeting_date: '2026-11-01',
}

describe('trending terms helpers (#1399)', () => {
  it('parses the chip sort, defaulting to rising', () => {
    expect(parseTrendSort('hot')).toBe('hot')
    expect(parseTrendSort('volume')).toBe('rising')
    expect(parseTrendSort(null)).toBe('rising')
  })

  it('labels the rise from the real shares, and a term new this year', () => {
    expect(riseLabel(t)).toBe('+100%')
    expect(riseLabel({ ...t, rise: 0.5 })).toBe('−50%')
    expect(riseLabel({ ...t, meetings_a: 0, share_a: 0, rise: null })).toBe('new this year')
    expect(riseLabel({ ...t, meetings_a: 0, share_a: 0, share_b: null, rise: null })).toBeNull()
  })

  it('builds an aria label from counts only', () => {
    const s = chipAriaLabel(t, 'rising', '2025', '2026')
    expect(s).toContain('sample term')
    expect(s).toContain('1% of recorded meetings in 2025')
    expect(s).toContain('12 governments')
    expect(chipAriaLabel(t, 'hot', '2025', '2026')).toContain('heated in public comment')
  })

  it('names the scope honestly: national, state, and a city answered by its state', () => {
    expect(trendScopeLabel(null, null)).toBe('National')
    expect(trendScopeLabel('Georgia', null)).toBe('Georgia')
    expect(trendScopeLabel('Alabama', 'Tuscaloosa')).toBe('Alabama (counted per state, not per city)')
  })

  it('formats the moment and links YouTube to it', () => {
    expect(clockLabel(65)).toBe('1:05')
    expect(clockLabel(3723)).toBe('1:02:03')
    expect(momentUrl('https://www.youtube.com/watch?v=abc', 90.4)).toBe('https://www.youtube.com/watch?v=abc&t=90s')
    expect(momentUrl('https://example.org/v/1', 90)).toBe('https://example.org/v/1')
    expect(momentUrl(null, 90)).toBeNull()
  })
})
