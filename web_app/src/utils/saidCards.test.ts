import { describe, expect, it } from 'vitest'
import { commentersLine, decisionsSummary, positionChips, saidSummary, speakerLine } from './saidCards'

// Test stand-ins, not warehouse figures.
const counts = {
  against: 0, for: 0, split: 0, silent: 9, unread: 0,
  vote_advanced: 4, vote_blocked: 0, vote_tabled: 0, with_person: 0, public_position_meetings: 0, in_passing: 5,
}

describe('positionChips', () => {
  it("labels a meeting-level position as the meeting's, in the topic's five-position words", () => {
    const chips = positionChips('water-fluoridation', { public_stance: 'against', public_position: 'oppose_local_choice', vote: null })
    expect(chips).toEqual([{ label: 'Public at this meeting: Oppose, each community decides', side: 'against', source: 'meeting' }])
  })
  it("uses the topic's own words for a lean (guns: named sides)", () => {
    const [c] = positionChips('guns', { public_stance: 'for', public_position: null, vote: null })
    expect(c!.label).toBe('Public at this meeting: Favor gun limits')
  })
  it('adds the body action as its own chip', () => {
    const chips = positionChips('water-fluoridation', { public_stance: 'silent', public_position: null, vote: 'advanced' })
    expect(chips).toEqual([{ label: 'Council or board: Voted to keep or start fluoridation', side: 'for', source: 'vote' }])
  })
  it('gives no chip without a source', () => {
    expect(positionChips('guns', { public_stance: 'silent', public_position: null, vote: null })).toEqual([])
    expect(positionChips('guns', { public_stance: null, public_position: null, vote: null })).toEqual([])
  })
})

describe('people lines', () => {
  it('names the speaker as served, or nothing', () => {
    expect(speakerLine({ speaker_display_name: 'Amy N.', speaker_role: 'Resident' })).toBe('Amy N. · Resident')
    expect(speakerLine({ speaker_display_name: null, speaker_role: 'Resident' })).toBeNull()
  })
  it('counts the commenters it does not list', () => {
    expect(commentersLine({ commenters: ['Ken C.', 'April W.', 'Fig M.'], commenter_count: 14 })).toBe(
      'Also spoke on it: Ken C., April W., Fig M. and 11 more',
    )
    expect(commentersLine({ commenters: [], commenter_count: 0 })).toBeNull()
  })
})

describe('saidSummary', () => {
  it('says the public took no position, the votes and the in-passing count (Georgia shape)', () => {
    expect(saidSummary('water-fluoridation', 9, counts)).toBe(
      'Of 9 meetings: the public took no position at any of them. A council or board acted at 4 (4 voted to keep or start fluoridation). 5 only mentioned it in passing.',
    )
  })
  it('lists the sides it has', () => {
    const line = saidSummary('guns', 10, { ...counts, against: 2, for: 3, split: 1, public_position_meetings: 6, vote_advanced: 0, with_person: 4, in_passing: 2 })
    expect(line).toContain('the public took a position at 6 (2 favor gun rights, 3 favor gun limits, 1 split)')
    expect(line).toContain('At 4, the record names who spoke.')
  })
  it('is null without counts', () => {
    expect(saidSummary('guns', 9, null)).toBeNull()
  })
})

describe('decisionsSummary', () => {
  it('splits on-topic from in passing', () => {
    expect(decisionsSummary(3, 6, 'gun control', 'guns')).toBe('3 decisions on gun control; 6 more mention guns in passing.')
    expect(decisionsSummary(0, 1, 'gun control', 'guns')).toBe('No decision on gun control itself; 1 decision mentions guns in passing.')
    expect(decisionsSummary(1, 0, 'gun control', 'guns')).toBe('1 decision on gun control.')
  })
})
