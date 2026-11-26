import { describe, expect, it } from 'vitest'
import { initialsOf, playLabel, quoteDate, recordedRole, resolveVideoId, startFromUrl } from './quoteCardUtils'

describe('resolveVideoId (#1108)', () => {
  it('keeps a given id', () => {
    expect(resolveVideoId('7VghnjHd_1w', 'https://example.gov/x')).toBe('7VghnjHd_1w')
  })
  it('derives the id from the first YouTube URL', () => {
    expect(resolveVideoId(null, null, 'https://example.gov/a.pdf', 'https://www.youtube.com/watch?v=7VghnjHd_1w&t=60s')).toBe('7VghnjHd_1w')
    expect(resolveVideoId(undefined, 'https://youtu.be/7VghnjHd_1w?t=12')).toBe('7VghnjHd_1w')
  })
  it('is null with no YouTube recording', () => {
    expect(resolveVideoId(null, 'https://example.gov/a.pdf', null)).toBeNull()
    expect(resolveVideoId('bad')).toBeNull()
  })
})

describe('startFromUrl', () => {
  it('reads t= in seconds or h/m/s', () => {
    expect(startFromUrl('https://www.youtube.com/watch?v=7VghnjHd_1w&t=7747s')).toBe(7747)
    expect(startFromUrl('https://youtu.be/7VghnjHd_1w?t=12')).toBe(12)
    expect(startFromUrl('https://www.youtube.com/watch?v=7VghnjHd_1w&t=1h2m5s')).toBe(3725)
  })
  it('is null without one', () => {
    expect(startFromUrl('https://www.youtube.com/watch?v=7VghnjHd_1w')).toBeNull()
    expect(startFromUrl(null)).toBeNull()
    expect(startFromUrl('nope')).toBeNull()
  })
})

describe('playLabel', () => {
  it('names the moment when known', () => {
    expect(playLabel(247)).toBe('Hear it at 4:07')
    expect(playLabel(3725)).toBe('Hear it at 1:02:05')
  })
  it('says Play recording without one', () => {
    expect(playLabel(null)).toBe('Play recording')
    expect(playLabel(0)).toBe('Play recording')
  })
})

describe('initialsOf', () => {
  it('takes first and last initials', () => {
    expect(initialsOf('Rob D.')).toBe('RD')
    expect(initialsOf('audra t.')).toBe('AT')
    expect(initialsOf('Mary Ann Smith')).toBe('MS')
  })
  it('handles one name and none', () => {
    expect(initialsOf('Rob')).toBe('R')
    expect(initialsOf('')).toBeNull()
    expect(initialsOf(null)).toBeNull()
    expect(initialsOf(' . ')).toBeNull()
  })
})

describe('quoteDate', () => {
  it('formats an ISO date', () => {
    expect(quoteDate('2026-05-07')).toBe('May 7, 2026')
    expect(quoteDate('2026-05-07T19:00:00Z')).toBe('May 7, 2026')
  })
  it('is null when missing', () => {
    expect(quoteDate(null)).toBeNull()
    expect(quoteDate('garbage')).toBeNull()
  })
})

describe('recordedRole', () => {
  it('keeps a real role and drops placeholders', () => {
    expect(recordedRole('Resident')).toBe('Resident')
    expect(recordedRole('Not stated')).toBeNull()
    expect(recordedRole('unknown')).toBeNull()
    expect(recordedRole('  ')).toBeNull()
    expect(recordedRole(null)).toBeNull()
  })
})
