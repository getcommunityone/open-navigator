import { describe, expect, it } from 'vitest'
import type { StanceQuestion } from '../api/stance'
import { answerChange, choiceBars, optionLabel, optionTone, questionPlace, questionText, titleWords } from './storyQuestion'

const q: StanceQuestion = {
  question_id: 'allow-new',
  version: 1,
  text: 'Should we allow new data centers?',
  place_text: 'Should {place} allow new data centers?',
  options: [
    { id: 'yes', label: 'Yes' },
    { id: 'no', label: 'No' },
    { id: 'moratorium', label: 'Pause for now' },
  ],
}
const nat = { stateName: null, city: null }
const al = { stateName: 'Alabama', city: null }
const tus = { stateName: 'Alabama', city: 'Tuscaloosa' }

describe('questionText', () => {
  it('names the place in scope, or nobody for the whole country', () => {
    expect(questionText(q, nat)).toBe('Should we allow new data centers?')
    expect(questionText(q, al)).toBe('Should Alabama allow new data centers?')
    expect(questionText(q, tus)).toBe('Should Tuscaloosa allow new data centers?')
    expect(questionPlace(nat)).toBeNull()
    // a city without a state is not a scope
    expect(questionPlace({ stateName: null, city: 'Tuscaloosa' })).toBeNull()
  })
})

describe('answerChange', () => {
  it('says whether the answer changed', () => {
    expect(answerChange(q, 'moratorium', 'no')).toEqual({ changed: true, sentence: 'You said Pause for now before. Now you say No.' })
    expect(answerChange(q, 'yes', 'yes')).toEqual({ changed: false, sentence: 'You said Yes both times.' })
  })
  it('does not compare with a skipped or unknown answer', () => {
    expect(answerChange(q, null, 'no')).toEqual({ changed: null, sentence: 'You said No. You skipped the question at the start.' })
    expect(answerChange(q, 'retired', 'no').changed).toBeNull()
    expect(answerChange(q, 'yes', null)).toEqual({ changed: null, sentence: null })
    expect(optionLabel(q, 'nope')).toBeNull()
  })
})

describe('choiceBars', () => {
  it('gives one bar per option with percentages that add up to 100', () => {
    const bars = choiceBars({ available: true, n: 3, counts: { yes: 1, no: 1, moratorium: 1 } }, q.options)!
    expect(bars.map((b) => b.id)).toEqual(['yes', 'no', 'moratorium'])
    expect(bars.reduce((a, b) => a + b.percent, 0)).toBe(100)
    expect(choiceBars({ available: true, n: 40, counts: { yes: 30, no: 10 } }, q.options)!.map((b) => [b.count, b.percent])).toEqual([
      [30, 75],
      [10, 25],
      [0, 0],
    ])
  })
  it('gives nothing for a withheld, missing or empty group', () => {
    expect(choiceBars({ available: false, n: 12, counts: null }, q.options)).toBeNull()
    expect(choiceBars(null, q.options)).toBeNull()
    expect(choiceBars(undefined, q.options)).toBeNull()
    expect(choiceBars({ available: true, n: 0, counts: { yes: 0, no: 0, moratorium: 0 } }, q.options)).toBeNull()
  })
  it('works for two options and for five', () => {
    const two = q.options.slice(0, 2)
    expect(choiceBars({ available: true, n: 3, counts: { yes: 2, no: 1 } }, two)!.map((b) => b.percent)).toEqual([67, 33])
    const five = ['a', 'b', 'c', 'd', 'e'].map((id) => ({ id, label: id.toUpperCase() }))
    const bars = choiceBars({ available: true, n: 7, counts: { a: 1, b: 1, c: 1, d: 1, e: 3 } }, five)!
    expect(bars).toHaveLength(5)
    expect(bars.reduce((a, b) => a + b.percent, 0)).toBe(100)
  })
  it('gives teal to the first option, amber to the second and a neutral tone to the rest', () => {
    expect([0, 1, 2, 3].map(optionTone)).toEqual(['agree', 'disagree', 'unsure', 'unsure'])
  })
})

describe('titleWords', () => {
  it('splits a headline into words', () => {
    expect(titleWords('Should  we allow\nnew data centers?')).toEqual(['Should', 'we', 'allow', 'new', 'data', 'centers?'])
    expect(titleWords('  ')).toEqual([])
  })
})
