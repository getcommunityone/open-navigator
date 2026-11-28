// API clients for the Data Center Story's "Over time" screen and the recording-coverage line (#1348).
//   GET /api/data-centers/sites-timeline?state=   every site (by appear_basis) + per-year totals by phase (SQL)
//   GET /api/coverage/recorded-meetings?state=&city=   the local governments and recorded meetings in scope
// Types are generated from the FastAPI schema (`npm run gen:api`). Years arrive as 4-digit strings (CLAUDE.md).
import type { components } from '../lib/api.types'
import api from '../lib/api'
import { withSpan } from '../instrumentation'

type Schemas = components['schemas']
export type SitesTimelineResponse = Schemas['SitesTimelineResponse']
export type TimelineSite = Schemas['TimelineSite']
export type TimelineYear = Schemas['TimelineYear']
export type RecordedCoverageResponse = Schemas['RecordedCoverageResponse']

/** Sites narrow by state only (the source places sites by state), so a city is never sent. */
export async function fetchSitesTimeline(stateCode?: string): Promise<SitesTimelineResponse> {
  return withSpan(
    'data-centers.sites-timeline.load',
    async (span) => {
      const res = await api.get<SitesTimelineResponse>('/data-centers/sites-timeline', { params: stateCode ? { state: stateCode } : {} })
      span.setAttribute('sites_timeline.dated', res.data?.dated ?? 0)
      return res.data
    },
    { 'data_centers.scope_level': stateCode ? 'state' : 'national' },
  )
}

export async function fetchRecordedCoverage(stateCode?: string, city?: string | null): Promise<RecordedCoverageResponse> {
  const params: Record<string, string> = {}
  if (stateCode) params.state = stateCode
  if (stateCode && city) params.city = city
  return withSpan(
    'coverage.recorded-meetings.load',
    async () => (await api.get<RecordedCoverageResponse>('/coverage/recorded-meetings', { params })).data,
    { 'coverage.scope_level': stateCode ? (city ? 'city' : 'state') : 'national' },
  )
}
