// Where towns stand (#1438): GET /api/rankings/topics and GET /api/rankings?topic=&band=&state= (#1437).
import api from '../lib/api'

export type SizeBand = 'large' | 'mid' | 'small' | 'unknown'
export type BandFilter = 'large' | 'mid' | 'small'

export interface RankingTopicSummary {
  topic_id: number
  slug: string
  name: string
  places_ranked: number
  places_unranked: number
  places_leaning_against: number
  places_leaning_for: number
  national_against_share: number | null
  median_shrunk_against_share: number | null
}

export interface RankingPlace {
  jurisdiction_id: string | number
  jurisdiction_name: string
  state_code: string
  size_band: SizeBand
  population: number | null
  speakers_for: number
  speakers_against: number
  meetings: number
  against_share: number
  shrunk_against_share: number
  is_ranked: boolean
  band_rank: number | null
  band_ranked_count: number | null
  officials_side: 'for' | 'against' | 'split' | null
  last_meeting_date: string | null
}

export interface RankingsResponse {
  topic: { topic_id: number; slug: string; name: string }
  national: {
    against_share: number | null
    median_shrunk_against_share: number | null
    places_ranked: number
    places_unranked: number
    places_leaning_against: number
    places_leaning_for: number
    speakers_for: number
    speakers_against: number
  }
  places: RankingPlace[]
}

export async function fetchRankingTopics(): Promise<RankingTopicSummary[]> {
  const res = await api.get<RankingTopicSummary[]>('/rankings/topics')
  return res.data
}

export async function fetchRankings(topic: string, band?: BandFilter, state?: string): Promise<RankingsResponse> {
  const params: Record<string, string> = { topic }
  if (band) params.band = band
  if (state) params.state = state
  const res = await api.get<RankingsResponse>('/rankings', { params })
  return res.data
}
