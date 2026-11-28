import { useMemo } from 'react'
import { useTopicTimeline } from '../stance/TimelineChart'
import type { InsightYear } from '../../utils/chartInsight'

/** The topic's real meetings per year in the scope, for a takeaway title (#1409); undefined while loading or unavailable. */
export function useInsightYears(topicSlug: string | undefined, stateCode?: string, city?: string | null): InsightYear[] | undefined {
  const q = useTopicTimeline(topicSlug ?? '', stateCode, city, Boolean(topicSlug))
  return useMemo(
    () => q.data?.years.map((y) => ({ year: y.year, meetings: y.meetings, share: y.share, recorded: y.all_recorded_meetings })),
    [q.data],
  )
}
