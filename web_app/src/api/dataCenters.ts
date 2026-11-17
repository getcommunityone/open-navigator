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
export type DataCenterSite = Schemas['DataCenterSite']
export type DataCenterSiteStatus = NonNullable<DataCenterSite['status']>
export type DataCenterSitesResponse = Schemas['DataCenterSitesResponse']
export type DataCenterAgendaItem = Schemas['DataCenterAgendaItem']
export type DataCenterAgendaItemsResponse = Schemas['DataCenterAgendaItemsResponse']
export type DataCenterMeetingMention = Schemas['DataCenterMeetingMention']
export type DataCenterMeetingMentionsResponse = Schemas['DataCenterMeetingMentionsResponse']
export type AreaConcern = Schemas['AreaConcern']
export type AreaConcernsResponse = Schemas['AreaConcernsResponse']

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

/** Data center sites (DC-4.1, #249): Epoch AI, CC BY 4.0. Narrows by state only. */
export async function fetchDataCenterSites(params: { state?: string }): Promise<DataCenterSitesResponse> {
  const q: Record<string, string> = {}
  if (params.state) q.state = params.state
  return withSpan(
    'data-centers.sites.load',
    async (span) => {
      const res = await api.get<DataCenterSitesResponse>('/data-centers/sites', { params: q })
      span.setAttribute('data_centers.sites.count', res.data?.items?.length ?? 0)
      return res.data
    },
    { 'data_centers.scope_level': params.state ? 'state' : 'national' },
  )
}

/** Agendas that mention a data center (DC-4.2, #250), upcoming meetings first. */
export async function fetchDataCenterAgendaItems(params: {
  state?: string
  city?: string
}): Promise<DataCenterAgendaItemsResponse> {
  const q: Record<string, string> = {}
  if (params.state) q.state = params.state
  if (params.city) q.city = params.city
  const scopeLevel = params.city ? 'city' : params.state ? 'state' : 'national'
  return withSpan(
    'data-centers.agenda-items.load',
    async (span) => {
      const res = await api.get<DataCenterAgendaItemsResponse>('/data-centers/agenda-items', { params: q })
      span.setAttribute('data_centers.agenda_items.count', res.data?.items?.length ?? 0)
      return res.data
    },
    { 'data_centers.scope_level': scopeLevel },
  )
}

/** What residents object to in their meetings (DC-4.3, #251), for the area and nationally. */
export async function fetchAreaConcerns(params: { state?: string; city?: string }): Promise<AreaConcernsResponse> {
  const q: Record<string, string> = {}
  if (params.state) q.state = params.state
  if (params.city) q.city = params.city
  const res = await api.get<AreaConcernsResponse>('/data-centers/concerns', { params: q })
  return res.data
}

/** Meeting passages where a data center was discussed (#445), quoted from the transcript. */
export async function fetchDataCenterMeetingMentions(params: {
  state?: string
  city?: string
}): Promise<DataCenterMeetingMentionsResponse> {
  const q: Record<string, string> = {}
  if (params.state) q.state = params.state
  if (params.city) q.city = params.city
  const scopeLevel = params.city ? 'city' : params.state ? 'state' : 'national'
  return withSpan(
    'data-centers.meeting-mentions.load',
    async (span) => {
      const res = await api.get<DataCenterMeetingMentionsResponse>('/data-centers/meeting-mentions', { params: q })
      span.setAttribute('data_centers.meeting_mentions.count', res.data?.items?.length ?? 0)
      return res.data
    },
    { 'data_centers.scope_level': scopeLevel },
  )
}
