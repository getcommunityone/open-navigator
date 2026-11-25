import { describe, expect, it } from 'vitest'
import type { StatementResults } from '../api/stance'
import { markerAt, readersRow, speakersRow } from './stanceContinuum'

// Test-only figures: nothing here is served by the app.
const group = (agree: number, disagree: number, unsure: number, available = true) => ({
  available,
  n: agree + disagree + unsure,
  agree: available ? agree : null,
  disagree: available ? disagree : null,
  unsure: available ? unsure : null,
})
const results = (over: Partial<StatementResults> = {}): StatementResults =>
  ({ statement_id: 's', statement_version: 1, your_answer: null, national: group(60, 30, 10), state: null, place: null, ...over }) as StatementResults

describe('readersRow (#981)', () => {
  it('uses the most specific group that reached the minimum sample, and places You in the middle of your answer', () => {
    const r = readersRow(results({ state: group(10, 30, 10) }), 20, 'disagree', { stateName: 'Texas', city: null })
    expect(r && 'row' in r).toBe(true)
    const row = (r as { row: { title: string; marker: number; sentence: string; segments: { key: string; percent: number }[] } }).row
    expect(row.title).toBe('Readers in Texas')
    expect(row.segments.map((s) => [s.key, s.percent])).toEqual([['agree', 20], ['unsure', 20], ['disagree', 60]])
    expect(row.marker).toBe(70)
    expect(row.sentence).toBe('You answered disagree, like 60% of 50 readers here.')
  })

  it('falls back to the country when the state has too few answers', () => {
    const r = readersRow(results({ state: group(1, 1, 0, false) }), 20, 'agree', { stateName: 'Texas', city: null })
    expect((r as { row: { title: string } }).row.title).toBe('Readers across the country')
  })

  it('says how many have answered when no group has reached the minimum sample', () => {
    const r = readersRow(results({ national: group(3, 2, 0, false) }), 20, 'agree', { stateName: null, city: null })
    expect(r).toEqual({ pending: { title: 'Readers across the country', n: 5, minSample: 20 } })
    expect(readersRow(undefined, 20, 'agree', { stateName: null, city: null })).toBeNull()
  })
})

describe('speakersRow (#981)', () => {
  const counts = { for: 3, against: 18, question: 1, neutral: 7 }

  it('places an agree answer on the side the statement leans to, and disagree on the other', () => {
    const agree = speakersRow(counts, 'for', 'agree', 'across the country')!
    expect(agree.segments.map((s) => s.key)).toEqual(['for', 'middle', 'against'])
    expect(agree.marker).toBe(markerAt(agree.segments, 'for'))
    expect(agree.sentence).toContain('who spoke for data centers')
    const disagree = speakersRow(counts, 'for', 'disagree', 'across the country')!
    expect(disagree.marker).toBe(markerAt(disagree.segments, 'against'))
    expect(disagree.sentence).toContain('the 18 speakers (62%) who spoke against data centers, of 29 speakers on record')
    expect(speakersRow(counts, 'against', 'agree', 'in Texas')!.marker).toBe(markerAt(agree.segments, 'against'))
  })

  it('puts not sure in the middle, with those who asked or took no side', () => {
    const r = speakersRow(counts, 'against', 'unsure', 'in Texas')!
    expect(r.marker).toBe(markerAt(r.segments, 'middle'))
    expect(r.title).toBe('Speakers at meetings in Texas')
  })

  it('is null without a lean, an answer or any speakers: no invented alignment', () => {
    expect(speakersRow(counts, null, 'agree', 'x')).toBeNull()
    expect(speakersRow(counts, 'for', null, 'x')).toBeNull()
    expect(speakersRow({ for: 0, against: 0, question: 0, neutral: 0 }, 'for', 'agree', 'x')).toBeNull()
    expect(speakersRow(null, 'for', 'agree', 'x')).toBeNull()
  })
})
