// API client for the flat meeting browse list (GET /api/meetings). Meeting-grain
// cards linked to topics/questions through transcripts; each card drills into its
// own decisions via fetchDecisions({ meetingId }).
import api from '../lib/api'

export type MeetingSort = 'recent' | 'interesting' | 'decisions'

export interface MeetingCard {
  meeting_id: number
  title: string | null
  jurisdiction: string | null
  city: string | null
  state_code: string | null
  state: string | null
  /** meeting_date coerced to ISO yyyy-mm-dd, or null. */
  date: string | null
  decision_count: number
  question_count: number
  has_decisions: boolean
  video_id: string | null
}

export interface MeetingListParams {
  /** CivicSearch topic id — meetings whose transcript matches the topic keywords. */
  topicId?: number
  /** Canonical AI theme slug — the fallback topic axis. */
  theme?: string
  /** Policy-question id — meetings that instantiate it (via their decisions). */
  questionId?: string
  /** 2-letter state code or full state name. */
  state?: string
  city?: string
  /** Free-text filter over meeting title / jurisdiction. */
  q?: string
  sort?: MeetingSort
  limit?: number
  offset?: number
}

export interface MeetingListResponse {
  items: MeetingCard[]
  pagination: { total: number; limit: number; offset: number }
}

/** Fetch a page of meeting cards, filtered/sorted server-side. Empty `items`
 *  (with total 0) is an honest "no meetings match" — never fabricated. */
export async function fetchMeetings(params: MeetingListParams = {}): Promise<MeetingListResponse> {
  const res = await api.get<MeetingListResponse>('/meetings', {
    params: {
      topic_id: params.topicId,
      theme: params.theme,
      question_id: params.questionId,
      state: params.state,
      city: params.city,
      q: params.q,
      sort: params.sort,
      limit: params.limit,
      offset: params.offset,
    },
  })
  return res.data
}
