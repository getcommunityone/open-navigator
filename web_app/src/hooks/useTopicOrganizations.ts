import { useQuery } from '@tanstack/react-query'
import { fetchTopicOrganizations, type TopicOrganizationsResponse } from '../api/topicOrganizations'

/** The nonprofits tied to a topic in a place (#1345): one cache entry shared by the story screen and its headline. */
export function useTopicOrganizations(topic: string, stateCode?: string | null, city?: string | null) {
  return useQuery<TopicOrganizationsResponse>({
    queryKey: ['topic-organizations', topic, stateCode ?? '', (stateCode && city) || ''],
    queryFn: () => fetchTopicOrganizations(topic, stateCode, city, 20),
    staleTime: 5 * 60_000,
    retry: 1,
  })
}
