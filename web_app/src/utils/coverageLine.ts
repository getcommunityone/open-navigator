// The recording-coverage line (#1348): how many local governments and recorded meetings sit behind a story's counts, so a
// small count ("10 meetings in Florida") reads as a count of our recordings, not of everything said. Every number comes from
// GET /api/coverage/recorded-meetings; when it is unavailable the line is not shown (never a made-up figure). No "of N"
// denominator: the jurisdictions mart counts census places as cities, so it is not a reliable count of governments
// (web_docs/docs/guides/data-stories.md, "Recording coverage").
import type { RecordedCoverageResponse } from '../api/sitesTimeline'

export interface CoverageScope {
  stateCode?: string
  stateName: string | null
  city: string | null
}

export interface CoverageText {
  /** The full sentence(s), for wide screens. */
  full: string
  /** A short form for phones. */
  short: string
}

const fmt = (n: number) => n.toLocaleString('en-US')
const govs = (n: number, place = '') => `${fmt(n)} ${place ? `${place} ` : ''}local ${n === 1 ? 'government' : 'governments'}`
const meetings = (n: number) => `${fmt(n)} ${n === 1 ? 'meeting' : 'meetings'}`

/** The line for the scope, or null when the counts are unavailable. */
export function coverageText(cov: RecordedCoverageResponse | null | undefined, scope: CoverageScope): CoverageText | null {
  if (!cov || !cov.available || cov.governments == null || cov.meetings == null) return null
  const g = cov.governments
  const m = cov.meetings
  const city = scope.stateCode ? scope.city : null
  if (city) {
    if (g === 0) return { full: `No ${city} local government is in our meeting recordings yet.`, short: `No ${city} recordings yet.` }
    return { full: `From recordings of ${govs(g, city)} (${meetings(m)}).`, short: `Recorded: ${meetings(m)}.` }
  }
  if (scope.stateCode) {
    const name = scope.stateName ?? scope.stateCode
    if (g === 0) return { full: `No ${name} local government is in our meeting recordings yet.`, short: `No ${scope.stateCode} recordings yet.` }
    return {
      full: `From recordings of ${govs(g, name)} (${meetings(m)}). Many ${name} governments aren't in our recordings yet.`,
      short: `Recorded: ${fmt(g)} ${scope.stateCode} ${g === 1 ? 'government' : 'governments'}, ${meetings(m)}.`,
    }
  }
  const states = cov.states && cov.states > 1 ? ` in ${fmt(cov.states)} states` : ''
  return {
    full: `From recordings of ${govs(g)}${states} (${meetings(m)}). Many governments aren't in our recordings yet.`,
    short: `Recorded: ${fmt(g)} governments, ${meetings(m)}.`,
  }
}
