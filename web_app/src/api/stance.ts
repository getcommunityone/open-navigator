// Client for the Data Center Challenge (#851 API, #852 screens, renamed in #884). Types are written by hand
// to match the Pydantic models in api/routes/stance.py.
import api from '../lib/api'
import {
  fetchAreaConcerns,
  fetchCommunityEvents,
  fetchDataCenterAgendaItems,
  fetchDataCenterDecisions,
  fetchDataCenterMeetingMentions,
  fetchDataCenterPositions,
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
  /** The Data Story screen that asks this statement (#981), e.g. `jobs`; absent when the story doesn't ask it. */
  story_screen?: string | null
  /** What agreeing lines up with among meeting speakers (#981); null when it lines up with neither side. */
  speaker_lean?: 'for' | 'against' | null
}

/** The one question a story asks before and after the record (#915). Absent on a pack without one. */
export interface StanceQuestion {
  question_id: string
  version: number
  /** The question for the whole country. */
  text: string
  /** The question for a place, with `{place}` where its name goes. */
  place_text: string
  options: Array<{ id: string; label: string }>
}

export interface StancePack {
  pack_id: string
  title: string
  version: number
  question?: StanceQuestion | null
  statements: StanceStatement[]
}

export type ChoiceMoment = 'before' | 'after'

/** `available` is true only at the minimum sample; otherwise `counts` is null and only `n` is real. */
export interface ChoiceGroup {
  available: boolean
  n: number
  counts: Record<string, number> | null
}

export interface ChoiceScopes {
  national: ChoiceGroup
  state: ChoiceGroup | null
  place: ChoiceGroup | null
}

export interface ChoiceResults {
  min_sample: number
  question_id: string
  question_version: number
  your: { before: string | null; after: string | null }
  before: ChoiceScopes
  after: ChoiceScopes
}

export interface StanceChoiceBody {
  player_id: string
  pack_id: string
  question_id: string
  moment: ChoiceMoment
  choice: string
  state_code?: string
  place_name?: string
}

export interface PostChoiceOut {
  stance_choice_response: {
    pack_id: string
    question_id: string
    question_version: number
    moment: ChoiceMoment
    choice: string
    state_code: string | null
    state: string | null
    place_name: string | null
  }
  results: ChoiceResults
}

export async function postStanceChoice(body: StanceChoiceBody): Promise<PostChoiceOut> {
  const res = await api.post<PostChoiceOut>('/stance/choices', body)
  return res.data
}

export async function fetchChoiceResults(
  packId: string,
  params: { stateCode?: string; placeName?: string; playerId?: string },
): Promise<ChoiceResults> {
  const res = await api.get<ChoiceResults>(`/stance/packs/${encodeURIComponent(packId)}/choice-results`, {
    params: { state_code: params.stateCode, place_name: params.placeName, player_id: params.playerId },
  })
  return res.data
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

/**
 * The dataset behind one chart, scoped to a state when one is chosen. The challenge never passes a city; the data stories
 * do, and every endpoint that can narrow to a city does (sites cannot: the source has no city field).
 */
export async function fetchChartData(key: string, stateCode?: string, city?: string): Promise<ChartData> {
  const c = stateCode && city ? city : undefined
  const p = { state: stateCode, city: c }
  // The record charts draw one dot per record, up to this many.
  const many = { state: stateCode, city: c, limit: DOT_CAP }
  switch (key as ChartKey) {
    case 'positions':
      return fetchDataCenterPositions(p)
    case 'job-claims':
      return fetchJobClaims(many)
    case 'sites':
      return fetchDataCenterSites({ state: stateCode, limit: DOT_CAP })
    case 'concerns':
      return fetchAreaConcerns(p)
    case 'meeting-mentions':
      return fetchDataCenterMeetingMentions(many)
    case 'agenda-items':
      return fetchDataCenterAgendaItems(many)
    case 'decisions':
      return fetchDataCenterDecisions(many)
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
