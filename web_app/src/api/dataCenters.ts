// API client for the data-center "Jobs promised" panel (issue #246, DC-1.1).
// Backs GET /api/data-centers/job-claims, which returns verbatim jobs claims
// made in public meetings, split by phase. No fabricated rows — an empty
// `items` array means no claims were found for the scope.
//
import type { components } from '../lib/api.types'
import api from '../lib/api'
import { withSpan } from '../instrumentation'

// Generated from the FastAPI schema (`npm run gen:api`), so the page and the API
// can't drift apart.
type Schemas = components['schemas']
export type JobClaim = Schemas['JobClaim']
export type JobClaimPhase = JobClaim['phase']
export type JobClaimsScope = Schemas['JobClaimScope']
export type JobClaimsResponse = Schemas['JobClaimsResponse']

export async function fetchJobClaims(params: {
  state?: string
  city?: string
}): Promise<JobClaimsResponse> {
  const q: Record<string, string> = {}
  if (params.state) q.state = params.state
  if (params.city) q.city = params.city
  const scopeLevel = params.city ? 'city' : params.state ? 'state' : 'national'
  // Low-cardinality attributes only (scope level, not the place name).
  return withSpan(
    'data-centers.job-claims.load',
    async (span) => {
      const res = await api.get<JobClaimsResponse>('/data-centers/job-claims', { params: q })
      span.setAttribute('data_centers.job_claims.count', res.data?.items?.length ?? 0)
      return res.data
    },
    { 'data_centers.scope_level': scopeLevel },
  )
}
