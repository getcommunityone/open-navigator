import { describe, expect, it } from 'vitest'
import { pickInsight, type InsightInput } from './chartInsight'

// Test-only fixtures: nothing here is served by the app.
const base: InsightInput = { subject: 'short-term rentals', place: 'Florida', totalMeetings: 47, topPlaces: ['Orange', 'Hillsborough'] }

describe('pickInsight', () => {
  it('leads with a rise in heat', () => {
    const r = pickInsight({ ...base, heatByYear: [{ year: '2025', mean: 1.4, rated: 40 }, { year: '2026', mean: 2.9, rated: 55 }], years: [] })
    expect(r.kind).toBe('heat')
    expect(r.title).toContain('getting heated')
    expect(r.title).toContain('doubled')
    expect(r.support).toContain('55 rated')
  })
  it('reports a fall in heat', () => {
    const r = pickInsight({ ...base, heatByYear: [{ year: '2025', mean: 3.8, rated: 40 }, { year: '2026', mean: 2.9, rated: 55 }] })
    expect(r.kind).toBe('heat')
    expect(r.title).toContain('cooling')
    expect(r.title).toContain('fell from 3.8 to 2.9 in 2026')
  })
  it('ignores a small dip in heat', () => {
    expect(pickInsight({ ...base, heatByYear: [{ year: '2025', mean: 3.7, rated: 100 }, { year: '2026', mean: 3.6, rated: 1321 }] }).kind).toBe('volume')
  })
  it('does not call thin heat data a headline', () => {
    expect(pickInsight({ ...base, heatByYear: [{ year: '2025', mean: 1, rated: 3 }, { year: '2026', mean: 3, rated: 4 }] }).kind).toBe('volume')
  })
  it('names officials siding against the public', () => {
    const r = pickInsight({ ...base, officials: { meetings: 6, read: 9 } })
    expect(r.kind).toBe('officials')
    expect(r.title).toBe('Florida officials sided against the public in 6 of 9 short-term rentals meetings')
  })
  it('ignores officials below the minimum', () => {
    expect(pickInsight({ ...base, officials: { meetings: 2, read: 3 } }).kind).toBe('volume')
  })
  it('reports a sharp rise in share, never a raw partial-year count', () => {
    const years = [{ year: '2025', meetings: 20, share: 0.02 }, { year: '2026', meetings: 18, share: 0.031 }]
    const r = pickInsight({ ...base, years })
    expect(r.kind).toBe('attention')
    expect(r.title).toContain('up 55%')
    expect(pickInsight({ ...base, years: [{ year: '2025', meetings: 20 }, { year: '2026', meetings: 40 }] }).kind).toBe('volume')
  })
  it('reports a clear public lean', () => {
    const r = pickInsight({ ...base, lean: { unit: 'meetings', against: 8, for: 1, other: 1 } })
    expect(r.kind).toBe('lean')
    expect(r.title).toBe('The public mostly opposed short-term rentals: 8 of 10 meetings where the public spoke')
  })
  it('adds the top concern only when the evidence is there', () => {
    const lean = { unit: 'speakers' as const, against: 30, for: 5, other: 5 }
    const withC = pickInsight({ ...base, lean, concern: { label: 'noise', count: 12, of: 30, basis: 'opposing' } })
    expect(withC.title).toContain('noise leads the complaints')
    expect(withC.support).toContain('12 of 30 opposing turns')
    const weak = pickInsight({ ...base, lean, concern: { label: 'noise', count: 2, of: 30, basis: 'opposing' } })
    expect(weak.title).not.toMatch(/leads|driven|because/)
    expect(pickInsight({ ...base, lean }).title).not.toMatch(/leads|driven|because/)
  })
  it('falls back to volume and place, then to a plain description', () => {
    expect(pickInsight(base).title).toBe('Short-term rentals came up in 47 meetings in Florida, most in Orange and Hillsborough')
    expect(pickInsight({ ...base, totalMeetings: 0 })).toMatchObject({ kind: 'none', title: 'Short-term rentals meetings · Florida' })
  })
  it('keeps titles near 90 characters', () => {
    const r = pickInsight({ ...base, subject: 'water fluoridation programs', place: 'the United States', lean: { unit: 'speakers', against: 30, for: 2, other: 0 }, concern: { label: 'health effects of the additive', count: 20, of: 30, basis: 'opposing' } })
    expect(r.title.length).toBeLessThanOrEqual(90)
  })
})
