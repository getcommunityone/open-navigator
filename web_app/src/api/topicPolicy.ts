// Where policy is moving on a topic (#1274): GET /api/topics/{topic}/legislation, /positions and /local-actions.
import api from '../lib/api'

export type BillStatus = 'enacted' | 'passed_chamber' | 'pending' | 'failed'

export interface LegislationBill {
  bill_id: string
  identifier: string | null
  title: string | null
  session: string | null
  /** Calendar year of the latest action, as a string (CLAUDE.md: bare years go on the wire as strings). */
  year: string | null
  category: string
  status: BillStatus
  passed_a_chamber: boolean
  url: string | null
  introduced_date: string | null
  last_action_date: string | null
  last_action: string | null
}

export interface LegislationState {
  state_code: string
  state: string | null
  top_status: BillStatus
  status_counts: Partial<Record<BillStatus, number>>
  bills: LegislationBill[]
}

export interface LegislationCategory {
  category: string
  label: string | null
  description: string | null
  display_order: number | null
  bills: number
}

export interface TopicLegislationResponse {
  topic: string
  topic_id: number | null
  state_code: string | null
  available: boolean
  total_bills: number
  states_with_bills: number
  status_counts: Partial<Record<BillStatus, number>>
  categories: LegislationCategory[]
  by_state: LegislationState[]
}

export interface PositionCount {
  key: string
  meetings: number
}

export interface TopicPositionsResponse {
  topic: string
  state_code: string | null
  available: boolean
  /** 'five' = the topic's own five positions; 'lean' = mostly supportive / mixed / mostly opposed. */
  scale: 'five' | 'lean' | null
  read_meetings: number
  spoke_meetings: number
  did_not_speak: number
  states: number
  options: PositionCount[]
}

export type ActionGroup = 'advanced' | 'blocked' | 'tabled_or_deferred'
export type ActionCounts = Record<ActionGroup, number>

export interface ActionMeeting {
  video_id: string
  jurisdiction_name: string | null
  state_code: string | null
  meeting_date: string | null
  outcome_group: ActionGroup
  outcome: string | null
  outcome_p: number | null
  url: string | null
  title: string | null
}

export interface TopicLocalActionsResponse {
  topic: string
  state_code: string | null
  available: boolean
  total: number
  undated: number
  totals: ActionCounts
  by_state: { state_code: string; state: string | null; counts: ActionCounts }[]
  by_year: { year: string; counts: ActionCounts }[]
  meetings: ActionMeeting[]
}

const params = (state?: string): Record<string, string> => (state ? { state } : {})

export async function fetchTopicLegislation(topic: string): Promise<TopicLegislationResponse> {
  // Always national: the map shows every state, and the scoped state is highlighted on the client.
  const res = await api.get<TopicLegislationResponse>(`/topics/${encodeURIComponent(topic)}/legislation`)
  return res.data
}

export async function fetchTopicPositions(topic: string, state?: string): Promise<TopicPositionsResponse> {
  const res = await api.get<TopicPositionsResponse>(`/topics/${encodeURIComponent(topic)}/positions`, { params: params(state) })
  return res.data
}

export async function fetchTopicLocalActions(topic: string, state?: string): Promise<TopicLocalActionsResponse> {
  const res = await api.get<TopicLocalActionsResponse>(`/topics/${encodeURIComponent(topic)}/local-actions`, {
    params: params(state),
  })
  return res.data
}
