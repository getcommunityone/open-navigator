/**
 * Letter grades for ACS Gini index of income inequality (household), raw 0–1 scale.
 * Lower Gini ⇒ more equal ⇒ better letter. Buckets are fixed (not percentile-based) so
 * the same value always maps to the same letter across map and scorecard.
 */
export type GiniLetter = 'A' | 'B' | 'C' | 'D' | 'F'

export type GiniLetterGrade = {
  letter: GiniLetter
  blurb: string
  letterClass: string
  blurbClass: string
  chipClass: string
}

/** Horizontal legend strip: letter + optional “ = …” tail (scorecard / map). */
export type GiniLetterStripRow = {
  letter: GiniLetter
  letterClass: string
  /** e.g. " = Very equal" — omit for middle letters to match compact layout */
  tail: string
}

export const GINI_LETTER_STRIP: readonly GiniLetterStripRow[] = [
  { letter: 'A', letterClass: 'text-emerald-700', tail: ' = Very equal' },
  { letter: 'B', letterClass: 'text-lime-700', tail: '' },
  { letter: 'C', letterClass: 'text-amber-700', tail: '' },
  { letter: 'D', letterClass: 'text-orange-700', tail: '' },
  { letter: 'F', letterClass: 'text-rose-700', tail: ' = High gap' },
] as const

const BUCKETS: { letter: GiniLetter; max: number; blurb: string; letterClass: string; blurbClass: string; chipClass: string }[] =
  [
    {
      letter: 'A',
      max: 0.43,
      blurb: 'Very equal',
      letterClass: 'text-emerald-700',
      blurbClass: 'text-emerald-800',
      chipClass: 'border-emerald-200 bg-emerald-50 text-emerald-900',
    },
    {
      letter: 'B',
      max: 0.455,
      blurb: 'More equal than typical',
      letterClass: 'text-lime-700',
      blurbClass: 'text-lime-900',
      chipClass: 'border-lime-200 bg-lime-50 text-lime-950',
    },
    {
      letter: 'C',
      max: 0.48,
      blurb: 'Typical inequality',
      letterClass: 'text-amber-700',
      blurbClass: 'text-amber-900',
      chipClass: 'border-amber-200 bg-amber-50 text-amber-950',
    },
    {
      letter: 'D',
      max: 0.505,
      blurb: 'Less equal than typical',
      letterClass: 'text-orange-700',
      blurbClass: 'text-orange-900',
      chipClass: 'border-orange-200 bg-orange-50 text-orange-950',
    },
    {
      letter: 'F',
      max: Infinity,
      blurb: 'High gap',
      letterClass: 'text-rose-700',
      blurbClass: 'text-rose-900',
      chipClass: 'border-rose-200 bg-rose-50 text-rose-950',
    },
  ]

/** Map / compact table: letter + numeric bucket hint + chip colors. */
export const GINI_CHOROPLETH_LEGEND_CHIPS: readonly { letter: GiniLetter; hint: string; chipClass: string }[] =
  BUCKETS.map((b) => ({
    letter: b.letter,
    hint: b.letter === 'F' ? '> 0.505' : `≤ ${b.max}`,
    chipClass: b.chipClass,
  }))

export function giniLetterGradeFromValue(gini: number | null | undefined): GiniLetterGrade | null {
  if (gini == null || !Number.isFinite(gini)) return null
  const g = gini
  for (const b of BUCKETS) {
    if (g <= b.max) {
      return {
        letter: b.letter,
        blurb: b.blurb,
        letterClass: b.letterClass,
        blurbClass: b.blurbClass,
        chipClass: b.chipClass,
      }
    }
  }
  const last = BUCKETS[BUCKETS.length - 1]!
  return {
    letter: last.letter,
    blurb: last.blurb,
    letterClass: last.letterClass,
    blurbClass: last.blurbClass,
    chipClass: last.chipClass,
  }
}

/** Short suffix for tooltips / compact values, e.g. `` · A``. */
export function giniLetterSuffix(gini: number | null | undefined): string {
  const m = giniLetterGradeFromValue(gini)
  return m ? ` · ${m.letter}` : ''
}
