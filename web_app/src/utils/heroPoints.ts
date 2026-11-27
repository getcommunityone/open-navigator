// The home Data stories hero's numbered points (#1122): titles fixed, every figure from the API (CLAUDE.md, No Fabricated
// Data). A point whose figure is missing or 0 is left out; nothing stands in for it.
import type { DataCenterPositionsResponse } from '../api/dataCenters'
import { countClauses } from './clauses'
import { speakerStateCount } from './dataStory'

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

/** A place's own figures for the points (#1134): its scoped lean totals and speaker sums, and how its name reads. */
export interface HeroPlace {
  label: string
  lean?: HeroLeanTotals | null
  speakers?: HeroSpeakerTotals | null
}

export interface HeroPointsOptions {
  /** States with any hand-counted speaker (from positions `by_state`), so the hand count names its scope (#1134). */
  speakerStates?: number | null
  /**
   * The page's place (#1134): each point uses the place's own figure where it is above 0, otherwise the national figure
   * prefixed "Nationally:" so it isn't read as the place's.
   */
  place?: HeroPlace | null
}

function speakerTotal(s: HeroSpeakerTotals | null | undefined): number {
  return num(s?.speakers_for) + num(s?.speakers_against) + num(s?.speakers_question) + num(s?.speakers_neutral)
}

/** "29 speakers counted by hand in 4 states: 18 against and 3 for." with zero sides left out (#1134); null for none. */
export function handCountLine(s: HeroSpeakerTotals | null | undefined, where: string): string | null {
  const total = speakerTotal(s)
  if (total < 1) return null
  const sides = countClauses(
    [
      { n: num(s?.speakers_against), text: (n) => `${n.toLocaleString('en-US')} against` },
      { n: num(s?.speakers_for), text: (n) => `${n.toLocaleString('en-US')} for` },
    ],
    { leadLarger: true },
  )
  return `${plural(total, 'speaker')} counted by hand${where}${sides ? `: ${sides}` : ''}.`
}

export function heroPoints(
  lean: HeroLeanTotals | null | undefined,
  speakers: HeroSpeakerTotals | null | undefined,
  opts: HeroPointsOptions = {},
): HeroPoint[] {
  const out: Omit<HeroPoint, 'n'>[] = []
  const place = opts.place ?? null
  const inPlace = place ? ` in ${place.label}` : ''
  const nat = (line: string) => (place ? `Nationally: ${line}` : line)

  // 1. Short, so it doesn't repeat the basis line under the title word for word (#1134).
  const pAgainst = num(place?.lean?.public_against_meetings)
  const against = num(lean?.public_against_meetings)
  const states = num(lean?.public_against_states)
  const pHand = place ? handCountLine(place.speakers, inPlace) : null
  const nHand = handCountLine(speakers, num(opts.speakerStates) > 0 ? ` in ${plural(num(opts.speakerStates), 'state')}` : '')
  let line1: string | null = null
  if (pAgainst > 0) line1 = `${plural(pAgainst, 'meeting')}${inPlace} where the public mostly opposed data centers (AI reading).`
  else if (pHand) line1 = pHand
  else if (against > 0) line1 = nat(`${plural(against, 'meeting')}${states > 0 ? ` across ${plural(states, 'state')}` : ''} where the public mostly opposed data centers (AI reading).`)
  else if (nHand) line1 = nat(nHand)
  if (line1) out.push({ icon: 'quote', title: 'Communities are saying no.', line: line1 })

  const pStopped = num(place?.lean?.stopped_meetings)
  const stopped = num(lean?.stopped_meetings)
  if (pStopped > 0 || stopped > 0) {
    out.push({
      icon: 'stop',
      title: 'Projects are being stopped.',
      line:
        pStopped > 0
          ? `${plural(pStopped, 'meeting')}${inPlace} tabled, denied or paused a data center (AI reading).`
          : nat(`${plural(stopped, 'meeting')} tabled, denied or paused a data center (AI reading).`),
    })
  }

  const pDisagree = num(place?.lean?.disagreement_meetings)
  const disagree = num(lean?.disagreement_meetings)
  if (pDisagree > 0 || disagree > 0) {
    out.push({
      icon: 'scale',
      title: "Officials don't always listen.",
      line:
        pDisagree > 0
          ? `Officials sided against the public in ${plural(pDisagree, 'meeting')}${inPlace} (AI reading).`
          : nat(`Officials sided against the public ${meetingsAcross(disagree, num(lean?.disagreement_states))} (AI reading).`),
    })
  }

  return out.map((p, i) => ({ ...p, n: i + 1 }))
}

/**
 * The points for a page (#1134), shared by the home hero and the story header: national figures from the national
 * positions response, and, on a place's page, the place's own from its scoped response (`scope_lean_totals`, `totals`).
 */
export function storyHeroPoints(
  national: DataCenterPositionsResponse | null | undefined,
  scoped: DataCenterPositionsResponse | null | undefined,
  placeLabel: string | null,
): HeroPoint[] {
  if (!national?.available) return []
  const place = placeLabel
    ? { label: placeLabel, lean: scoped?.available ? scoped.scope_lean_totals : null, speakers: scoped?.available ? scoped.totals : null }
    : null
  return heroPoints(national.lean_totals, national.totals, { speakerStates: speakerStateCount(national), place })
}
