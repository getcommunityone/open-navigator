// The home Data stories hero's numbered points (#1122): titles fixed, every figure from the API (CLAUDE.md, No Fabricated
// Data). A point whose figure is missing or 0 is left out; nothing stands in for it.

/** National totals of Jev's meeting readings (`positions.lean_totals`); AI readings of transcripts, not counted speakers. */
export interface HeroLeanTotals {
  public_against_meetings?: number | null
  public_against_states?: number | null
  stopped_meetings?: number | null
  disagreement_meetings?: number | null
  disagreement_states?: number | null
}

/** National counted-speaker sums (`positions.totals`). */
export interface HeroSpeakerTotals {
  speakers_for?: number | null
  speakers_against?: number | null
  speakers_question?: number | null
  speakers_neutral?: number | null
}

export type HeroPointIcon = 'quote' | 'stop' | 'scale'

export interface HeroPoint {
  /** 1-based number shown beside the point, in the order shown (a left-out point doesn't leave a gap). */
  n: number
  icon: HeroPointIcon
  title: string
  line: string
}

const num = (v: number | null | undefined): number => (typeof v === 'number' && Number.isFinite(v) && v > 0 ? v : 0)

/** "1 meeting", "1,234 meetings". */
export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n.toLocaleString('en-US')} ${n === 1 ? one : many}`
}

/** "in 12 meetings across 5 states"; the states part is dropped when the state count is 0. */
function meetingsAcross(meetings: number, states: number): string {
  return `in ${plural(meetings, 'meeting')}${states > 0 ? ` across ${plural(states, 'state')}` : ''}`
}

export interface HeroPointsOptions {
  /** States with any hand-counted speaker (from positions `by_state`), so the hand count names its scope (#1134). */
  speakerStates?: number | null
  /** True when the page is scoped to a place: every line then starts "Nationally:" so it isn't read as the place's (#1134). */
  nationally?: boolean
}

export function heroPoints(
  lean: HeroLeanTotals | null | undefined,
  speakers: HeroSpeakerTotals | null | undefined,
  opts: HeroPointsOptions = {},
): HeroPoint[] {
  const out: Omit<HeroPoint, 'n'>[] = []

  const against = num(lean?.public_against_meetings)
  const sAgainst = num(speakers?.speakers_against)
  const sTotal = num(speakers?.speakers_for) + sAgainst + num(speakers?.speakers_question) + num(speakers?.speakers_neutral)
  const parts: string[] = []
  if (against > 0) {
    parts.push(
      `The public leaned against data centers ${meetingsAcross(against, num(lean?.public_against_states))} (AI reading of meetings).`,
    )
  }
  if (sTotal >= 1) {
    const states = num(opts.speakerStates)
    parts.push(
      `${plural(sTotal, 'speaker')} counted by hand${states > 0 ? ` in ${plural(states, 'state')}` : ''}: ` +
        `${sAgainst.toLocaleString('en-US')} against, ${num(speakers?.speakers_for).toLocaleString('en-US')} for.`,
    )
  }
  if (parts.length) out.push({ icon: 'quote', title: 'Communities are saying no.', line: parts.join(' ') })

  const stopped = num(lean?.stopped_meetings)
  if (stopped > 0) {
    out.push({
      icon: 'stop',
      title: 'Projects are being stopped.',
      line: `${plural(stopped, 'meeting')} tabled, denied or paused a data center (AI reading).`,
    })
  }

  const disagree = num(lean?.disagreement_meetings)
  if (disagree > 0) {
    out.push({
      icon: 'scale',
      title: "Officials don't always listen.",
      line: `Officials sided against the public ${meetingsAcross(disagree, num(lean?.disagreement_states))} (AI reading).`,
    })
  }

  return out.map((p, i) => ({ ...p, n: i + 1, line: opts.nationally ? `Nationally: ${p.line}` : p.line }))
}
