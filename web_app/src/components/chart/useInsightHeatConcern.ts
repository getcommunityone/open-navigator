import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { InsightInput } from '../../utils/chartInsight'
import { fetchTopicHeatByYear, fetchTopicTopConcern } from '../../api/topics'
import { toConcern, toHeatByYear } from './insightFacts'

/**
 * Per-year speaker heat and the top concern for the scope (#1418). Each is undefined while loading, on error or when the
 * server omitted it for too few rated speakers or turns, so the picker's heat and "leads the complaints" findings fire
 * only from real data that met the thresholds.
 */
export function useInsightHeatConcern(
  topicSlug: string | undefined,
  stateCode?: string,
  city?: string | null,
): Pick<InsightInput, 'heatByYear' | 'concern'> {
  const c = stateCode && city ? city : ''
  const heat = useQuery({
    queryKey: ['topic-heat-by-year', topicSlug, stateCode ?? 'national', c],
    queryFn: () => fetchTopicHeatByYear(topicSlug ?? '', stateCode, c || undefined),
    enabled: Boolean(topicSlug),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  const top = useQuery({
    queryKey: ['topic-top-concern', topicSlug, stateCode ?? 'national', c],
    queryFn: () => fetchTopicTopConcern(topicSlug ?? '', stateCode, c || undefined),
    enabled: Boolean(topicSlug),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  return useMemo(() => ({ heatByYear: toHeatByYear(heat.data), concern: toConcern(top.data) }), [heat.data, top.data])
}
