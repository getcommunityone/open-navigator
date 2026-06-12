// API client for the flat decision browse list (GET /api/decisions). Returns the
// SAME card shape as /api/lenses (Contested-lens cards), so the Topics /
// Questions / States browse pages and search can all render the shared StoryCard.
import api from '../lib/api'
import type { ApiCard } from '../components/StoryLenses'

export type DecisionSort = 'contested' | 'recent' | 'interesting'

export interface DecisionListParams {
  /** civicsearch topic id — fuzzy text match against decision search_tsv. */
  topicId?: number
  /** policy-question id — exact link via question_instance. */
  questionId?: string
  /** 2-letter state code or full state name. */
  state?: string
  city?: string
  /** Free-text filter over decision title/summary/theme/jurisdiction. */
  q?: string
  sort?: DecisionSort
  limit?: number
  offset?: number
}

export interface DecisionListResponse {
  items: ApiCard[]
  pagination: { total: number; limit: number; offset: number }
}

/** Fetch a page of decision cards, filtered/sorted server-side. Empty `items`
 *  (with total 0) is an honest "no decisions match" — never fabricated. */
export async function fetchDecisions(params: DecisionListParams = {}): Promise<DecisionListResponse> {
  const res = await api.get<DecisionListResponse>('/decisions', {
    params: {
      topic_id: params.topicId,
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
