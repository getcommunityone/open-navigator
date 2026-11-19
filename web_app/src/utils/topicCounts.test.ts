import { describe, expect, it } from 'vitest'
import { topicCountTitle, topicMeetingCountLabel } from './topicCounts'

describe('topicMeetingCountLabel', () => {
  it('spells out the unit with a real count', () => {
    expect(topicMeetingCountLabel(19648)).toBe('19,648 meetings')
    expect(topicMeetingCountLabel(1)).toBe('1 meeting')
    expect(topicMeetingCountLabel(0)).toBe('0 meetings')
  })

  it('shows a dash, not a number, when the API sent none', () => {
    expect(topicMeetingCountLabel(null)).toBe('—')
    expect(topicMeetingCountLabel(undefined)).toBe('—')
    expect(topicMeetingCountLabel(Number.NaN)).toBe('—')
  })
})

describe('topicCountTitle', () => {
  it('names the place the count covers', () => {
    expect(topicCountTitle('AL')).toBe('Meetings whose transcript mentions this topic in AL')
    expect(topicCountTitle('GA', 'Atlanta')).toBe(
      'Meetings whose transcript mentions this topic in Atlanta, GA',
    )
    expect(topicCountTitle(undefined)).toBe('Meetings whose transcript mentions this topic nationally')
  })
})
