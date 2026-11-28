import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchTopicsYoy, type YoyResponse } from '../api/topicsYoy'
import { buildHotPills, type LiveChip } from '../utils/hotTopics'

/** The yoy query the hero pills and Browse all topics share (one cache entry per place). */
export const yoyQueryKey = (state?: string | null, city?: string | null) => ['topics-yoy', state ?? '', (state && city) || '']

/**
 * The home hero's pills (#1416): live stories plus the rising and heated topics for the place, from the same
 * `/api/topics/yoy` response Browse all topics reads. Recomputed per `?state=&city=`. While it loads (or if it fails) the
 * row is the live stories, never a placeholder.
 */
export function useHotTopics(live: LiveChip[], stateCode?: string | null, city?: string | null) {
  const q = useQuery<YoyResponse>({
    queryKey: yoyQueryKey(stateCode, city),
    queryFn: () => fetchTopicsYoy(stateCode ?? undefined, stateCode ? city : null),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  const pills = useMemo(() => buildHotPills(live, q.data), [live, q.data])
  return { pills, yoy: q.data, pending: q.isPending, failed: q.isError }
}
