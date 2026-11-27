import { useQuery } from '@tanstack/react-query'
import { fetchTopicOutcomes, type TopicOutcomesResponse } from '../api/topicOutcomes'

/** The chain from meeting to outcome (#1314): one cache entry for the screen, its headline and the home card. */
export function useTopicOutcomes(topic: string, stateCode?: string | null, city?: string | null) {
  return useQuery<TopicOutcomesResponse>({
    queryKey: ['topic-outcomes', topic, stateCode ?? '', (stateCode && city) || ''],
    queryFn: () => fetchTopicOutcomes(topic, stateCode, city),
    staleTime: 5 * 60_000,
    retry: 1,
  })
}
