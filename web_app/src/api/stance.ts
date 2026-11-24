// Client for the "Where Do You Stand?" game (#851 API, #852 screens). Types are written by hand
// to match the Pydantic models in api/routes/stance.py.
import api from '../lib/api'
import {
  fetchAreaConcerns,
  fetchCommunityEvents,
  fetchDataCenterAgendaItems,
  fetchDataCenterMeetingMentions,
  fetchDataCenterProjects,
  fetchDataCenterSites,
  fetchJobClaims,
} from './dataCenters'
import { DOT_CAP, type ChartData, type ChartKey } from '../utils/stanceGame'

export type StanceAnswer = 'agree' | 'disagree' | 'unsure'

export interface StanceStatement {
  statement_id: string
  version: number
  order: number
  category: string
  statement: string
  chart: ChartKey | string
}

export interface StancePack {
  pack_id: string
  title: string
  version: number
  statements: StanceStatement[]
}

export interface PackSummary {
  pack_id: string
  title: string
  version: number
  statement_count: number
}

/** `available` is true only at the minimum sample; otherwise the three counts are null and only `n` is real. */
export interface GroupResult {
  available: boolean
  n: number
  agree: number | null
  disagree: number | null
  unsure: number | null
}

export interface StatementResults {
  statement_id: string
  statement_version: number
  your_answer: StanceAnswer | null
  national: GroupResult
  state: GroupResult | null
  place: GroupResult | null
}

export interface PackResults {
  min_sample: number
  statements: StatementResults[]
}

export interface StanceResponseBody {
  player_id: string
  pack_id: string
  statement_id: string
  answer: StanceAnswer
  state_code?: string
  place_name?: string
}

export interface PostResponseOut {
  stance_response: {
    pack_id: string
    statement_id: string
    statement_version: number
    answer: StanceAnswer
    state_code: string | null
    state: string | null
    place_name: string | null
  }
  results: StatementResults
}

export async function fetchStancePacks(): Promise<PackSummary[]> {
  const res = await api.get<PackSummary[]>('/stance/packs')
  return res.data
}

export async function fetchStancePack(packId: string): Promise<StancePack> {
  const res = await api.get<StancePack>(`/stance/packs/${encodeURIComponent(packId)}`)
  return res.data
}

export async function postStanceResponse(body: StanceResponseBody): Promise<PostResponseOut> {
  const res = await api.post<PostResponseOut>('/stance/responses', body)
  return res.data
}

export async function fetchStanceResults(
  packId: string,
  params: { stateCode?: string; placeName?: string; playerId?: string },
): Promise<PackResults> {
  const res = await api.get<PackResults>(`/stance/packs/${encodeURIComponent(packId)}/results`, {
    params: { state_code: params.stateCode, place_name: params.placeName, player_id: params.playerId },
  })
  return res.data
}

/** The dataset behind one round's chart, scoped to the player's state when one is chosen (never to a city). */
export async function fetchChartData(key: string, stateCode?: string): Promise<ChartData> {
  const p = { state: stateCode }
  // The record charts draw one dot per record, up to this many.
  const many = { state: stateCode, limit: DOT_CAP }
  switch (key as ChartKey) {
    case 'job-claims':
      return fetchJobClaims(p)
    case 'sites':
      return fetchDataCenterSites(many)
    case 'concerns':
      return fetchAreaConcerns(p)
    case 'meeting-mentions':
      return fetchDataCenterMeetingMentions(many)
    case 'agenda-items':
      return fetchDataCenterAgendaItems(many)
    case 'community-events':
      return fetchCommunityEvents(many)
    case 'projects':
      return fetchDataCenterProjects(p)
    default:
      throw new Error(`Unknown chart ${key}`)
  }
}

/** HTTP status of a failed api call, if the client attached one. */
export function errorStatus(e: unknown): number | null {
  const s = (e as { response?: { status?: number } } | null)?.response?.status
  return typeof s === 'number' ? s : null
}
