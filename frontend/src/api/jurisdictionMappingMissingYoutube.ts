/** Live drill-down for jurisdictions missing a golden YouTube channel URL. */

export type MissingYoutubeDrillEntity = 'cities' | 'towns' | 'counties'

export type MissingYoutubeDrillParams = {
  entity: MissingYoutubeDrillEntity
  state_code?: string
  acs_population_tier?: string
  acs_income_level?: string
  limit?: number
  offset?: number
}

export type MissingYoutubeDrillRow = {
  jurisdiction_id: string
  name: string
  state_code: string
  jurisdiction_type: string
  geoid?: string | null
  municipality_place_kind?: string | null
  primary_website_url?: string | null
  has_primary_website?: boolean | null
  n_youtube_channel_rows?: number | null
  acs_population_tier?: string | null
  acs_income_level?: string | null
}

export type MissingYoutubeDrillResponse = {
  entity: string
  state_code: string | null
  acs_population_tier: string | null
  acs_income_level: string | null
  total: number
  limit: number
  offset: number
  rows: MissingYoutubeDrillRow[]
}

export async function fetchMissingYoutubeChannels(
  params: MissingYoutubeDrillParams,
  signal?: AbortSignal,
): Promise<MissingYoutubeDrillResponse> {
  const u = new URL('/api/jurisdiction-mapping/missing-youtube-channel', window.location.origin)
  u.searchParams.set('entity', params.entity)
  if (params.state_code) u.searchParams.set('state_code', params.state_code)
  if (params.acs_population_tier) u.searchParams.set('acs_population_tier', params.acs_population_tier)
  if (params.acs_income_level) u.searchParams.set('acs_income_level', params.acs_income_level)
  if (params.limit != null) u.searchParams.set('limit', String(params.limit))
  if (params.offset != null) u.searchParams.set('offset', String(params.offset))

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
  return (await res.json()) as MissingYoutubeDrillResponse
}
