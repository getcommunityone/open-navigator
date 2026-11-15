import { describe, expect, it } from 'vitest'
import { formatTimestamp, meetingMomentPath, parseTimestamp } from './timestamp'

describe('parseTimestamp', () => {
  it.each([
    ['754', 754],
    ['754.9', 754],
    ['12m34s', 754],
    ['1h2m3s', 3723],
    ['2h', 7200],
    ['45s', 45],
    ['12:34', 754],
    ['1:02:03', 3723],
    ['0', 0],
  ])('reads %s as %d seconds', (value, seconds) => {
    expect(parseTimestamp(value)).toBe(seconds)
  })

  it.each([null, '', '  ', 'abc', '-5', '1:2:3:4', '12:75', 'm', '1h2x'])('rejects %s', (value) => {
    expect(parseTimestamp(value as string | null)).toBeNull()
  })
})

describe('formatTimestamp', () => {
  it.each([
    [0, '0:00'],
    [45, '0:45'],
    [754, '12:34'],
    [3723, '1:02:03'],
    [754.9, '12:34'],
    [-3, '0:00'],
  ])('formats %d as %s', (seconds, text) => {
    expect(formatTimestamp(seconds)).toBe(text)
  })
})

describe('meetingMomentPath', () => {
  it('links to the second, rounded down', () => {
    expect(meetingMomentPath('abc123', 754.9)).toBe('/meetings/abc123?t=754')
  })

  it('links to the meeting when the time is unknown', () => {
    expect(meetingMomentPath('abc123', null)).toBe('/meetings/abc123')
  })

  it('encodes the meeting id', () => {
    expect(meetingMomentPath('a b/c', 5)).toBe('/meetings/a%20b%2Fc?t=5')
  })
})
