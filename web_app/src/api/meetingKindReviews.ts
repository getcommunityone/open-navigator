/** Admin meeting-kind review / override client (#668). */
import api from '../lib/api'
import { withSpan } from '../instrumentation'

export type MeetingKindSource = 'transcript' | 'meta'
export type MeetingKindSort = 'not_government_p' | 'keep_score' | 'screened_at'
export type OverrideKind =
  | 'government_meeting'
  | 'town_hall'
  | 'government_other'
  | 'not_government'

export interface MeetingKindReviewItem {
  video_id: string
  title: string | null
  state_code: string | null
  jurisdiction_id: string | null
  source: MeetingKindSource
  meeting_kind: string | null
  not_government_p: number | null
  keep_score: number | null
  screened_at: string | null
  youtube_url: string
  override_kind: string | null
  override_note: string | null
  effective_kind: string | null
}

export interface MeetingKindReviewsResponse {
  items: MeetingKindReviewItem[]
  total: number
  source: MeetingKindSource
  kind: string
}

export interface MeetingKindOverrideOut {
  video_id: string
  override_kind: string
  note: string | null
  overridden_by: string | null
  overridden_at: string
}

export async function fetchMeetingKindReviews(params: {
  source?: MeetingKindSource
  kind?: string
  sort?: MeetingKindSort
  order?: 'asc' | 'desc'
  state?: string
  limit?: number
  offset?: number
}): Promise<MeetingKindReviewsResponse> {
  return withSpan('admin.meeting-kind-reviews.load', async () => {
    const res = await api.get<MeetingKindReviewsResponse>('/admin/meeting-kind-reviews', {
      params: {
        source: params.source ?? 'transcript',
        kind: params.kind ?? 'not_government',
        sort: params.sort ?? 'not_government_p',
        order: params.order ?? 'desc',
        state: params.state || undefined,
        limit: params.limit ?? 100,
        offset: params.offset ?? 0,
      },
    })
    return res.data
  })
}

export async function putMeetingKindOverride(
  videoId: string,
  body: { override_kind: OverrideKind; note?: string | null },
): Promise<MeetingKindOverrideOut> {
  const res = await api.put<MeetingKindOverrideOut>(
    `/admin/meeting-kind-overrides/${encodeURIComponent(videoId)}`,
    body,
  )
  return res.data
}

export async function deleteMeetingKindOverride(videoId: string): Promise<void> {
  await api.delete(`/admin/meeting-kind-overrides/${encodeURIComponent(videoId)}`)
}
