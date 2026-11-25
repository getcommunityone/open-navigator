import { describe, expect, it } from 'vitest'
import { ASK_PAUSE_MS, askAfterMs, roundBeat, roundStop } from './stanceGame'

describe('roundBeat', () => {
  it('starts on the finding and moves to the question once asked', () => {
    expect(roundBeat({ answered: false, asked: false })).toBe('finding')
    expect(roundBeat({ answered: false, asked: true })).toBe('question')
  })
  it('shows the results for a confirmed answer, even if the question was never asked on this visit', () => {
    expect(roundBeat({ answered: true, asked: false })).toBe('results')
    expect(roundBeat({ answered: true, asked: true })).toBe('results')
  })
  it('goes back to the question while the player changes an answer', () => {
    expect(roundBeat({ answered: true, asked: true, changing: true })).toBe('question')
    expect(roundBeat({ answered: true, asked: false, changing: true })).toBe('question')
  })
  it('waits only the pause, with no drawing, under reduced motion', () => {
    expect(askAfterMs(true)).toBe(ASK_PAUSE_MS)
    expect(askAfterMs(false)).toBeGreaterThan(ASK_PAUSE_MS)
  })
})

describe('roundStop', () => {
  it('maps finding → finding, question → question, results → reveal', () => {
    expect(roundStop('finding')).toBe('finding')
    expect(roundStop('question')).toBe('question')
    expect(roundStop('results')).toBe('reveal')
  })
  it('follows roundBeat for a fresh, asked, and answered round', () => {
    expect(roundStop(roundBeat({ answered: false, asked: false }))).toBe('finding')
    expect(roundStop(roundBeat({ answered: false, asked: true }))).toBe('question')
    expect(roundStop(roundBeat({ answered: true, asked: true }))).toBe('reveal')
    expect(roundStop(roundBeat({ answered: true, asked: true, changing: true }))).toBe('question')
  })
})
