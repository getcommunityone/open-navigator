import { describe, expect, it } from 'vitest'
import { advocacyMeetingCountLabel } from './advocacyMeetingCount'

describe('advocacyMeetingCountLabel', () => {
  it('formats a positive count', () => {
    expect(advocacyMeetingCountLabel(1)).toBe('1 related meeting')
    expect(advocacyMeetingCountLabel(5200)).toBe('5,200 related meetings')
  })

  it('returns null when the count is missing or not positive', () => {
    expect(advocacyMeetingCountLabel(null)).toBeNull()
    expect(advocacyMeetingCountLabel(undefined)).toBeNull()
    expect(advocacyMeetingCountLabel(0)).toBeNull()
    expect(advocacyMeetingCountLabel(-1)).toBeNull()
  })
})
