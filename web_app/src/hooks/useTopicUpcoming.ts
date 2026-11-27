import { useQuery } from '@tanstack/react-query'
import { fetchTopicUpcoming, type TopicUpcomingResponse } from '../api/topicUpcoming'

/** What is coming up on a topic (#1302): one cache entry shared by the story screen, its headline and the home card. */
export function useTopicUpcoming(topic: string, stateCode?: string | null, city?: string | null) {
  return useQuery<TopicUpcomingResponse>({
    queryKey: ['topic-upcoming', topic, stateCode ?? '', (stateCode && city) || ''],
    queryFn: () => fetchTopicUpcoming(topic, stateCode, city, 24),
    staleTime: 5 * 60_000,
    retry: 1,
  })
}
