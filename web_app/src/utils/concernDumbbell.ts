// #1209: rows for the Concerns screen's dumbbell. Each concern's share of the place's mentions against its share of the
// nation's mentions, or, nationally, a single share of mentions: the mart has no per-concern objection count
// (`objection_count` is the area's total objections, repeated on every row), so there is no second national value.
import type { AreaConcernsResponse } from '../api/dataCenters'
import { concernLabel } from '../lib/dataCenterJobs'
import { cap, concernList } from './stanceGame'

/** A concern needs at least this many mentions in the place to get a row; fewer is one passage, too thin to compare. */
export const MIN_PLACE_MENTIONS = 2

export interface ConcernRow {
  key: string
  label: string
  /** Share of all national mentions (0–1), or null on the national screen, where there is nothing to compare with. */
  national: number | null
  /** Share of all of the place's mentions (0–1); nationally, the national share. */
  place: number
  placeMentions: number
  nationalMentions: number
}

export interface ConcernRows {
  /** 'compare': place against the nation. 'single': one share per concern (the national screen, or no national rows). */
  mode: 'compare' | 'single'
  rows: ConcernRow[]
  /** Labels of the concerns left out: fewer than MIN_PLACE_MENTIONS mentions in the place (zero included, when raised nationally). */
  hidden: string[]
  placeTotal: number
  nationalTotal: number
}

export type ConcernSort = 'place' | 'difference' | 'national'

const counts = (list: Array<{ concern: string; mention_count: number }>) => {
  const m = new Map<string, number>()
  for (const c of list) if (c.mention_count > 0) m.set(c.concern, (m.get(c.concern) ?? 0) + c.mention_count)
  return m
}

/**
 * The dumbbell's rows from the real concerns response. `place` is the scope's label (null nationally). Shares divide by
 * every mention in the scope, hidden concerns included, so leaving a row out never inflates the others.
 */
export function buildConcernRows(res: AreaConcernsResponse | null | undefined, place: string | null, min = MIN_PLACE_MENTIONS): ConcernRows {
  const nat = counts(res ? concernList(res, null) : [])
  const here = place ? counts(res ? concernList(res, place) : []) : nat
  const sum = (m: Map<string, number>) => [...m.values()].reduce((a, n) => a + n, 0)
  const nationalTotal = sum(nat)
  const placeTotal = sum(here)
  const mode: ConcernRows['mode'] = place && nationalTotal > 0 ? 'compare' : 'single'
  const rows: ConcernRow[] = []
  const hidden: Array<[string, number]> = []
  for (const key of new Set([...here.keys(), ...(mode === 'compare' ? nat.keys() : [])])) {
    const n = here.get(key) ?? 0
    if (n < min || placeTotal <= 0) {
      hidden.push([key, n])
      continue
    }
    const nn = nat.get(key) ?? 0
    rows.push({
      key,
      label: cap(concernLabel(key)),
      national: mode === 'compare' ? nn / nationalTotal : null,
      place: n / placeTotal,
      placeMentions: n,
      nationalMentions: nn,
    })
  }
  hidden.sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
  return { mode, rows: sortConcernRows(rows, 'place'), hidden: hidden.map(([k]) => concernLabel(k)), placeTotal, nationalTotal }
}

/** By the place's share, by difference from the nation (largest rise first) or by the national share; label breaks ties. */
export function sortConcernRows(rows: ConcernRow[], by: ConcernSort): ConcernRow[] {
  const v = (r: ConcernRow) => (by === 'place' ? r.place : by === 'national' ? (r.national ?? r.place) : r.place - (r.national ?? r.place))
  return [...rows].sort((a, b) => v(b) - v(a) || a.label.localeCompare(b.label))
}
