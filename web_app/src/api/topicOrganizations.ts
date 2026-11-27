// The nonprofits tied to a topic (#1345): GET /api/topics/{topic}/organizations.
import api from '../lib/api'

/** How an organization is tied to the topic, strongest first. */
export type OrgMatchMethod = 'named_in_meeting' | 'keyword_in_mission' | 'keyword_in_name' | 'ntee_code' | 'cause_tag'

export interface TopicOrganizationItem {
  master_org_id: string
  org_name: string
  city: string | null
  state_code: string | null
  state: string | null
  match_method: OrgMatchMethod
  match_methods: OrgMatchMethod[]
  /** The evidence: a meeting passage or the mission with the topic's words in <mark>, or the IRS category's name. */
  match_text: string | null
  /** named_in_meeting: the meeting's recording, its date and place. */
  match_source_url: string | null
  match_date: string | null
  match_place: string | null
  /** The 990 mission statement, when the organization files one. */
  mission: string | null
  /** Only when the name or mission states the position outright; otherwise null and none is shown. */
  side: string | null
  ntee_code: string | null
  revenue: number | null
  /** The tax year of `revenue`, as a string. */
  revenue_tax_year: string | null
  website_url: string | null
}

export interface TopicOrganizationsResponse {
  topic: string
  topic_id: number | null
  state_code: string | null
  state: string | null
  city: string | null
  available: boolean
  total: number
  counts: Record<OrgMatchMethod, number>
  items: TopicOrganizationItem[]
  broader: { state_code: string | null; label: string; total: number } | null
  built_at: string | null
  /** True when the counts may be short (a city counted from the served rows of a state that has more, #1382). */
  partial?: boolean
}

export async function fetchTopicOrganizations(
  topic: string,
  stateCode?: string | null,
  city?: string | null,
  limit = 12,
): Promise<TopicOrganizationsResponse> {
  const params: Record<string, string | number> = { limit }
  if (stateCode) params.state = stateCode
  if (stateCode && city) params.city = city
  const { data } = await api.get<TopicOrganizationsResponse>(`/topics/${encodeURIComponent(topic)}/organizations`, { params })
  return data
}
