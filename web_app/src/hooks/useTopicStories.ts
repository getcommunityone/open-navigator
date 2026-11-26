import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchTopics } from '../api/topics'
import { deriveTopicStories, liveStories } from '../utils/topicStories'

/**
 * The live topic stories (#1133), from the national topic catalog: curated topics with linked meetings. Read nationally on
 * purpose: whether a story exists does not depend on the page's place (the story itself shows an empty place honestly).
 */
export function useTopicStories() {
  const q = useQuery({ queryKey: ['topics', 'catalog', 'national'], queryFn: () => fetchTopics(), staleTime: 10 * 60_000, retry: 1 })
  const stories = useMemo(() => deriveTopicStories(q.data), [q.data])
  const live = useMemo(() => liveStories(stories), [stories])
  return { topics: q.data, stories, live, pending: q.isPending, failed: q.isError }
}
