// What is coming up on a topic (#1302): GET /api/topics/{topic}/upcoming.
import api from '../lib/api'

export type UpcomingKind = 'meeting' | 'hearing' | 'deadline' | 'bill_action'
/** Why the item is about the topic: the agenda names it, an official hearing notice, or the place discussed it before. */
export type UpcomingBasis = 'agenda_text' | 'official_notice' | 'place_discussed_before'

export interface UpcomingItem {
  upcoming_id: string
  kind: UpcomingKind
  match_basis: UpcomingBasis
  /** ISO date, today or later. */
  date: string
  time: string | null
  jurisdiction_name: string | null
  state_code: string
  state: string | null
  body_name: string | null
  title: string | null
  location: string | null
  /** Where to take part: the agenda, the meeting page, the livestream or the official notice. */
  source_url: string
  source_label: string
  /** Verbatim evidence with the topic's words in <mark> (render with highlightSnippet). */
  matched_text: string
  /** place_discussed_before: the earlier recorded meeting the evidence comes from. */
  prior_meeting_date: string | null
  prior_url: string | null
  tentative: boolean
}

export interface PendingBill {
  bill_id: string
  identifier: string | null
  title: string | null
  state_code: string
  state: string | null
  status: 'pending' | 'passed_chamber'
  last_action: string | null
  last_action_date: string | null
  url: string | null
}

export interface TopicUpcomingResponse {
  topic: string
  topic_id: number | null
  state_code: string | null
  state: string | null
  city: string | null
  available: boolean
  as_of: string
  last_updated: string | null
  built_at: string | null
  total: number
  counts: Record<UpcomingKind, number>
  items: UpcomingItem[]
  pending_bills: { total: number; latest_action_seen: string | null; items: PendingBill[] }
  /** Set when the scope has nothing upcoming: the count one level up (city -> state -> national). */
  broader: { state_code: string | null; label: string; total: number } | null
}

export async function fetchTopicUpcoming(topic: string, stateCode?: string | null, city?: string | null, limit = 12): Promise<TopicUpcomingResponse> {
  const params: Record<string, string | number> = { limit }
  if (stateCode) params.state = stateCode
  if (stateCode && city) params.city = city
  const { data } = await api.get<TopicUpcomingResponse>(`/topics/${encodeURIComponent(topic)}/upcoming`, { params })
  return data
}
