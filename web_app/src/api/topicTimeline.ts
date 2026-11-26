// Topic timeline + period dumbbell (#1140): GET /api/topics/{topic}/timeline and /period-compare.
import api from '../lib/api'

export interface TimelineYear {
  /** Calendar year as a string (CLAUDE.md: bare years go on the wire as strings). */
  year: string
  meetings: number
  passages: number | null
  all_recorded_meetings: number | null
  /** meetings / all_recorded_meetings (0–1), null when it can't be computed. */
  share: number | null
}

export type MilestoneKind = 'approved' | 'denied' | 'tabled' | 'moratorium' | 'bill_enacted'

export interface TimelineMilestone {
  date: string
  kind: MilestoneKind
  place: string | null
  state_code: string | null
  title: string | null
  url: string | null
  video_id?: string | null
  /** ai_reading: a classifier's reading of the transcript; record: an official record (a bill). */
  source: 'ai_reading' | 'record'
}

export interface TimelineScope {
  level: 'national' | 'state' | 'city'
  state_code: string | null
  state: string | null
  city: string | null
}

export interface TopicTimelineResponse {
  topic: string
  topic_name: string | null
  scope: TimelineScope
  years: TimelineYear[]
  undated_meetings: number
  total_meetings: number
  total_passages: number | null
  milestones: TimelineMilestone[]
  coverage_available: boolean
  bills_available: boolean
}

export interface PeriodRow {
  key: string
  label: string
  earlier_share: number
  later_share: number
  earlier_meetings: number
  later_meetings: number
  earlier_recorded: number
  later_recorded: number
}

export interface PeriodCompareResponse {
  topic: string
  scope: TimelineScope
  from_year: string
  to_year: string
  grain: 'state' | 'place'
  min_recorded_meetings: number
  min_topic_meetings: number
  hidden_rows: number
  rows: PeriodRow[]
}

export async function fetchTopicTimeline(topic: string, state?: string, city?: string | null): Promise<TopicTimelineResponse> {
  const params: Record<string, string> = {}
  if (state) params.state = state
  if (state && city) params.city = city
  const res = await api.get<TopicTimelineResponse>(`/topics/${encodeURIComponent(topic)}/timeline`, { params })
  return res.data
}

export async function fetchPeriodCompare(topic: string, state?: string, from?: string, to?: string): Promise<PeriodCompareResponse> {
  const params: Record<string, string> = {}
  if (state) params.state = state
  if (from) params.from = from
  if (to) params.to = to
  const res = await api.get<PeriodCompareResponse>(`/topics/${encodeURIComponent(topic)}/period-compare`, { params })
  return res.data
}
