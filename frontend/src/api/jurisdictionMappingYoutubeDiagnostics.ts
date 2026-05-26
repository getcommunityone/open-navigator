/** Live YouTube channel / bronze video diagnostics per jurisdiction. */

export type YoutubeDiagnosticsEntity = 'counties' | 'cities' | 'towns'

export type YoutubeChannelDiagnosticsParams = {
  entity: YoutubeDiagnosticsEntity
  state_code: string
  name_search?: string
  limit?: number
}

export type YoutubeChannelGoldenRow = {
  youtube_channel_url?: string | null
  youtube_channel_id?: string | null
  channel_title?: string | null
  is_primary?: boolean
  discovery_method?: string | null
  verified_at?: string | null
}

export type YoutubeChannelCandidateRow = {
  youtube_channel_url?: string | null
  youtube_channel_id?: string | null
  channel_title?: string | null
  is_verified?: boolean
  discovery_method?: string | null
  official_meeting_confidence?: number | null
  rejection_reason?: string | null
}

export type YoutubeChannelDiagnosticsRow = {
  jurisdiction_id: string
  name: string
  state_code: string
  jurisdiction_type: string
  geoid?: string | null
  primary_website_url?: string | null
  has_primary_website?: boolean
  has_youtube_channel: boolean
  youtube_channel_url?: string | null
  youtube_channel_id?: string | null
  youtube_discovery_method?: string | null
  n_golden_channel_rows: number
  n_candidates: number
  n_verified_candidates: number
  n_bronze_videos: number
  gap_reason_code: string
  gap_reason_label: string
  golden_channels: YoutubeChannelGoldenRow[]
  candidate_channels: YoutubeChannelCandidateRow[]
}

export type YoutubeChannelDiagnosticsResponse = {
  entity: string
  state_code: string
  name_search: string | null
  total: number
  rows: YoutubeChannelDiagnosticsRow[]
  explained?: Record<string, string>
}

export type YoutubeChannelCoverageParams = {
  entity: YoutubeDiagnosticsEntity
  state_code?: string
}

export type YoutubeChannelCoverageResponse = {
  entity: string
  state_code: string | null
  total: number
  with_youtube_channel: number
  pct_with_youtube_channel: number
  source: string
}

export async function fetchYoutubeChannelCoverage(
  params: YoutubeChannelCoverageParams,
  signal?: AbortSignal,
): Promise<YoutubeChannelCoverageResponse> {
  const u = new URL('/api/jurisdiction-mapping/youtube-channel-coverage', window.location.origin)
  u.searchParams.set('entity', params.entity)
  if (params.state_code?.trim()) u.searchParams.set('state_code', params.state_code.trim().toUpperCase())

  const res = await fetch(u.toString(), { credentials: 'include', signal })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = (await res.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  return (await res.json()) as YoutubeChannelCoverageResponse
}

export async function fetchYoutubeChannelDiagnostics(
  params: YoutubeChannelDiagnosticsParams,
  signal?: AbortSignal,
): Promise<YoutubeChannelDiagnosticsResponse> {
  const u = new URL('/api/jurisdiction-mapping/youtube-channel-diagnostics', window.location.origin)
  u.searchParams.set('entity', params.entity)
  u.searchParams.set('state_code', params.state_code)
  if (params.name_search) u.searchParams.set('name_search', params.name_search)
  if (params.limit != null) u.searchParams.set('limit', String(params.limit))

  const res = await fetch(u.toString(), { credentials: 'include', signal })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = (await res.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  return (await res.json()) as YoutubeChannelDiagnosticsResponse
}
