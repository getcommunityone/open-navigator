import type { DataCenterPositionsResponse } from '../api/dataCenters'
import { positionFigures, storyScopeLabel, type StoryScope, type StoryStat } from './dataStory'

const n = (v: number) => v.toLocaleString('en-US')
const plural = (v: number, one: string, many = `${one}s`) => `${n(v)} ${v === 1 ? one : many}`

/**
 * The phone summary card's facts (#1337): up to three short lines, each a real count from the story's own data. A fact whose
 * data is missing is left out; nothing is estimated or filled in.
 */
export function summaryFacts(stats: StoryStat[], positions: DataCenterPositionsResponse | null | undefined, scope: StoryScope, subject = 'data centers'): string[] {
  const out: string[] = []
  const place = scope.stateName ? storyScopeLabel(scope) : 'the United States'
  const meetings = stats.find((s) => s.key === 'meetings')?.value
  if (meetings) out.push(`${plural(meetings, 'meeting')} in ${place} mentioned ${subject}`)
  const fig = positionFigures(positions, scope)
  if (fig) {
    const v = (k: string) => fig.find((f) => f.key === k)?.value ?? null
    const f = v('for')
    const a = v('against')
    const q = v('question')
    if (f != null && a != null && q != null && f + a + q > 0) {
      const parts = [a > 0 ? `${n(a)} against` : '', f > 0 ? `${n(f)} for` : '', q > 0 ? `${n(q)} with questions` : ''].filter(Boolean)
      out.push(`${plural(f + a + q, 'person', 'people')} spoke on it: ${parts.join(', ')}`)
    }
    const vf = v('votes_for')
    const va = v('votes_against')
    if (vf != null && va != null) out.push(`Recorded votes by officials: ${n(vf)} for, ${n(va)} against`)
  }
  return out.slice(0, 3)
}

/** One figure of the phone Overview's stat row (#1380): the number big, a short label under it. */
export interface SummaryStat {
  value: string
  label: string
}

/**
 * The phone Overview's stat row: at most two real figures, the number and a small label. The meeting count first; then
 * the recorded official votes, else the people who spoke. A figure whose data is missing is left out; nothing is filled in.
 */
export function summaryStats(stats: StoryStat[], positions: DataCenterPositionsResponse | null | undefined, scope: StoryScope, subject = 'data centers'): SummaryStat[] {
  const out: SummaryStat[] = []
  const place = scope.stateName ? storyScopeLabel(scope) : 'the United States'
  const meetings = stats.find((s) => s.key === 'meetings')?.value
  if (meetings) out.push({ value: n(meetings), label: `${meetings === 1 ? 'meeting' : 'meetings'} in ${place} mentioned ${subject}` })
  const fig = positionFigures(positions, scope)
  if (fig) {
    const v = (k: string) => fig.find((f) => f.key === k)?.value ?? null
    const vf = v('votes_for')
    const va = v('votes_against')
    if (vf != null && va != null) out.push({ value: `${n(vf)}–${n(va)}`, label: 'recorded votes by officials, for–against' })
    else {
      const f = v('for')
      const a = v('against')
      const q = v('question')
      if (f != null && a != null && q != null && f + a + q > 0) out.push({ value: n(f + a + q), label: `${f + a + q === 1 ? 'person' : 'people'} spoke on it` })
    }
  }
  return out.slice(0, 2)
}
