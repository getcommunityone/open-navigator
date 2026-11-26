// Pure logic for the question a data story opens and closes on (#915): the wording for a place, whether the reader's answer
// changed, and the bar maths for any number of options. Nothing here invents a count: a group below the minimum sample has no
// bars at all.
import type { ChoiceGroup, StanceQuestion } from '../api/stance'
import { largestRemainder } from './matrixMapMath'

interface PlaceScope {
  stateName: string | null
  city: string | null
}

/** The place the question names: the city, else the state, else nobody in particular (the whole country). */
export function questionPlace(scope: PlaceScope): string | null {
  if (!scope.stateName) return null
  return scope.city ?? scope.stateName
}

/** "Should we allow new data centers?" nationally, "Should Tuscaloosa allow new data centers?" for a place. */
export function questionText(q: Pick<StanceQuestion, 'text' | 'place_text'>, scope: PlaceScope): string {
  const place = questionPlace(scope)
  return place ? q.place_text.replace('{place}', place) : q.text
}

/** The label of an option id, or null when the id is not one of the question's options. */
export function optionLabel(q: Pick<StanceQuestion, 'options'> | null | undefined, id: string | null | undefined): string | null {
  if (!q || !id) return null
  return q.options.find((o) => o.id === id)?.label ?? null
}

export interface AnswerChange {
  /** True: the two answers differ. False: the same. Null: there are not two answers to compare. */
  changed: boolean | null
  /** One plain sentence for the reader, or null when there is no answer after the story. */
  sentence: string | null
}

/** "You said Pause for now before. Now you say No." / "You said Yes both times." / "You said No. You skipped the question at the start." */
export function answerChange(q: Pick<StanceQuestion, 'options'>, before: string | null | undefined, after: string | null | undefined): AnswerChange {
  const a = optionLabel(q, after)
  if (!a) return { changed: null, sentence: null }
  const b = optionLabel(q, before)
  if (!b) return { changed: null, sentence: `You said ${a}. You skipped the question at the start.` }
  if (before === after) return { changed: false, sentence: `You said ${a} both times.` }
  return { changed: true, sentence: `You said ${b} before. Now you say ${a}.` }
}

export interface ChoiceBar {
  id: string
  label: string
  count: number
  /** Whole percentages that add up to 100 (largest remainder). */
  percent: number
}

/** One bar per option, in the question's order, or null when the group is withheld, missing or empty. */
export function choiceBars(group: ChoiceGroup | null | undefined, options: StanceQuestion['options']): ChoiceBar[] | null {
  if (!group || !group.available || !group.counts) return null
  const counts = options.map((o) => Math.max(0, group.counts?.[o.id] ?? 0))
  if (counts.reduce((x, y) => x + y, 0) <= 0) return null
  const pct = largestRemainder(counts, 100)
  if (pct.length === 0) return null
  return options.map((o, i) => ({ id: o.id, label: o.label, count: counts[i]!, percent: pct[i]! }))
}

/** The tone of an option's bar: the first is the house teal, the second its opposite pole (amber), the rest a neutral ink. */
export function optionTone(index: number): 'agree' | 'disagree' | 'unsure' {
  return index === 0 ? 'agree' : index === 1 ? 'disagree' : 'unsure'
}

/** A headline split into words for the rising-title entrance. Runs of spaces collapse; an empty headline gives no words. */
export function titleWords(text: string): string[] {
  return text.split(/\s+/).filter(Boolean)
}
