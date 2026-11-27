// What happened next on a topic (#1314): GET /api/topics/{topic}/outcomes.
import api from '../lib/api'

export interface OutcomeExample {
  id: string
  title: string | null
  date: string | null
  state_code: string | null
  jurisdiction_name: string | null
  url: string | null
  /** A verbatim line (<mark>ed when it is matched text) or the reading's label. */
  detail: string | null
}

export interface OutcomeStep {
  available: boolean
  count: number
  examples: OutcomeExample[]
}

export interface TopicOutcomesResponse {
  topic: string
  state_code: string | null
  state: string | null
  city: string | null
  steps: {
    meetings: OutcomeStep
    public: OutcomeStep & { read: number; silent: number; by_lean: Partial<Record<'opposed' | 'mixed' | 'supportive', number>> }
    actions: OutcomeStep & { by_outcome: Partial<Record<'advanced' | 'blocked' | 'moratorium' | 'tabled', number>> }
    bills: OutcomeStep & { by_status: Partial<Record<'enacted' | 'passed_chamber' | 'pending' | 'failed', number>> }
    linked_bills: OutcomeStep & { bills: number; by_method: Record<string, number> }
    next: OutcomeStep & { upcoming: number; pending_bills: number }
  }
}

export async function fetchTopicOutcomes(topic: string, stateCode?: string | null, city?: string | null): Promise<TopicOutcomesResponse> {
  const params: Record<string, string> = {}
  if (stateCode) params.state = stateCode
  if (stateCode && city) params.city = city
  const { data } = await api.get<TopicOutcomesResponse>(`/topics/${encodeURIComponent(topic)}/outcomes`, { params })
  return data
}
