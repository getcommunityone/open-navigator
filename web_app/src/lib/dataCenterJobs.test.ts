import { describe, expect, it } from 'vitest'
import {
  dataCentersTitle,
  formatDateRange,
  formatHeadcount,
  hearItUrl,
  meetingAttribution,
  placeScope,
  verifiedLabel,
} from './dataCenterJobs'

describe('formatHeadcount', () => {
  it('says "Not stated" when both bounds are unknown (never 0)', () => {
    expect(formatHeadcount(null, null)).toBe('Not stated')
  })
  it('renders a range', () => {
    expect(formatHeadcount(100, 1500)).toBe('100–1,500 jobs')
  })
  it('renders a single number when low equals high or one bound is missing', () => {
    expect(formatHeadcount(120, 120)).toBe('120 jobs')
    expect(formatHeadcount(50, null)).toBe('At least 50 jobs')
    expect(formatHeadcount(null, 75)).toBe('Up to 75 jobs')
  })
  it('keeps a real zero distinct from unknown', () => {
    expect(formatHeadcount(0, 0)).toBe('0 jobs')
  })
})

describe('placeScope / dataCentersTitle', () => {
  it('is National with no filter', () => {
    expect(dataCentersTitle(placeScope(undefined, undefined))).toBe('Data centers · National')
  })
  it('expands a state code to the full name', () => {
    expect(dataCentersTitle(placeScope('AL', undefined))).toBe('Data centers · Alabama')
  })
  it('uses the city when a city filter is applied', () => {
    expect(dataCentersTitle(placeScope('AL', 'Tuscaloosa'))).toBe('Data centers · Tuscaloosa')
  })
})

describe('formatDateRange / hearItUrl', () => {
  it('says "Dates not stated" when both are null', () => {
    expect(formatDateRange(null, null)).toBe('Dates not stated')
  })
  it('floors the start second in the YouTube link', () => {
    expect(hearItUrl('abc123', 754.9)).toBe('https://www.youtube.com/watch?v=abc123&t=754s')
    expect(hearItUrl(null, 10)).toBeNull()
    expect(hearItUrl('abc123', null)).toBeNull()
  })
})

describe('meetingAttribution (DC-1.2)', () => {
  it('names the governing body when the record has one', () => {
    expect(meetingAttribution('Tuscaloosa City Council')).toBe('At the Tuscaloosa City Council meeting')
  })
  it('never guesses a body', () => {
    expect(meetingAttribution(null)).toBe('Meeting record')
    expect(meetingAttribution('   ')).toBe('Meeting record')
  })
})

describe('verifiedLabel (DC-1.3)', () => {
  it('shows the verified date when fresh', () => {
    expect(verifiedLabel('2026-11-15T14:00:00Z', false)).toBe('Verified Nov 15, 2026')
  })
  it('flags a stale link and keeps its last date', () => {
    expect(verifiedLabel('2026-09-01T00:00:00Z', true)).toBe('Not verified in the last 30 days (last verified Sep 1, 2026)')
  })
  it('says when a link was never verified', () => {
    expect(verifiedLabel(null, true)).toBe('Not verified yet')
  })
})
