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

// --- who spoke for and against, and the recorded votes (#930) ------------------------------------------------------
// Written by hand to match `DataCenterPositionsResponse` in api/routes/data_centers.py; `npm run gen:api` adds the same
// shapes to api.types.ts.

export interface PositionTotals {
  /** Meetings the counts come from. */
  meetings: number | null
  /** Analysed meetings in scope where a data center came up. */
  meetings_reviewed: number | null
  speakers_for: number | null
  speakers_against: number | null
  speakers_question: number | null
  speakers_neutral: number | null
  decisions_with_tally: number | null
  /** Null (never 0) when no decision recorded a tally. */
  votes_for: number | null
  votes_against: number | null
}

export interface PositionQuote {
  public_comment_id: string
  /** The speaker's own words, verbatim from the transcript. */
  quote: string
  speaker_role?: string | null
  jurisdiction_name?: string | null
  state_code?: string | null
  meeting_date?: string | null
  video_url?: string | null
  start_seconds?: number | null
  jump_url?: string | null
  /** The data center decision the comment is linked to, when that is why it counts. */
  decision_headline?: string | null
  match_basis?: 'data_center_decision' | 'own_words' | null
}

export interface DataCenterPositionsResponse {
  scope: Schemas['JobClaimScope']
  /** False when the table is not in the database yet: every total is null, not zero. */
  available: boolean
  totals: PositionTotals
  quotes: { for: PositionQuote[]; against: PositionQuote[]; question: PositionQuote[] }
}

/** Public speakers for and against a data center item, questions asked and recorded votes, for the scope (#930). */
export async function fetchDataCenterPositions(params: {
  state?: string
  city?: string
  limit?: number
}): Promise<DataCenterPositionsResponse> {
  const q: Record<string, string> = {}
  if (params.limit) q.limit = String(params.limit)
  if (params.state) q.state = params.state
  if (params.city) q.city = params.city
  const scopeLevel = params.city ? 'city' : params.state ? 'state' : 'national'
  return withSpan(
    'data-centers.positions.load',
    async (span) => {
      const res = await api.get<DataCenterPositionsResponse>('/data-centers/positions', { params: q })
      span.setAttribute('data_centers.positions.available', res.data?.available === true)
      return res.data
    },
    { 'data_centers.scope_level': scopeLevel },
  )
}
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
export type CommunityEvent = Schemas['CommunityEvent']
export type CommunityEventsResponse = Schemas['CommunityEventsResponse']
export type DataCenterProject = Schemas['DataCenterProject']
export type DataCenterProjectsResponse = Schemas['DataCenterProjectsResponse']

export async function fetchJobClaims(params: {
  state?: string
  city?: string
  limit?: number
}): Promise<JobClaimsResponse> {
  const q: Record<string, string> = {}
  if (params.limit) q.limit = String(params.limit)
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
export async function fetchDataCenterSites(params: { state?: string; limit?: number }): Promise<DataCenterSitesResponse> {
  const q: Record<string, string> = {}
  if (params.state) q.state = params.state
  if (params.limit) q.limit = String(params.limit)
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
  limit?: number
}): Promise<DataCenterAgendaItemsResponse> {
  const q: Record<string, string> = {}
  if (params.limit) q.limit = String(params.limit)
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
  limit?: number
}): Promise<DataCenterMeetingMentionsResponse> {
  const q: Record<string, string> = {}
  if (params.limit) q.limit = String(params.limit)
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

/** Company-hosted data center meetings found in news and press releases (#532). */
export async function fetchCommunityEvents(params: {
  state?: string
  city?: string
  projectId?: string
  limit?: number
}): Promise<CommunityEventsResponse> {
  const q: Record<string, string> = {}
  if (params.limit) q.limit = String(params.limit)
  if (params.state) q.state = params.state
  if (params.city) q.city = params.city
  if (params.projectId) q.project_id = params.projectId
  const scopeLevel = params.city ? 'city' : params.state ? 'state' : 'national'
  return withSpan(
    'data-centers.community-events.load',
    async (span) => {
      const res = await api.get<CommunityEventsResponse>('/data-centers/community-events', { params: q })
      span.setAttribute('data_centers.community_events.count', res.data?.items?.length ?? 0)
      return res.data
    },
    { 'data_centers.scope_level': scopeLevel },
  )
}

/** Data center projects with companies, sourced figures and a timeline (#531/#532). */
export async function fetchDataCenterProjects(params: {
  state?: string
  city?: string
  source?: 'curated' | 'epoch'
}): Promise<DataCenterProjectsResponse> {
  const q: Record<string, string> = {}
  if (params.state) q.state = params.state
  if (params.city) q.city = params.city
  if (params.source) q.source = params.source
  const scopeLevel = params.city ? 'city' : params.state ? 'state' : 'national'
  return withSpan(
    'data-centers.projects.load',
    async (span) => {
      const res = await api.get<DataCenterProjectsResponse>('/data-centers/projects', { params: q })
      span.setAttribute('data_centers.projects.count', res.data?.items?.length ?? 0)
      return res.data
    },
    { 'data_centers.scope_level': scopeLevel },
  )
}
