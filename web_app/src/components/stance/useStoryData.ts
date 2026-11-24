import { useMemo } from 'react'
import { useQueries } from '@tanstack/react-query'
import { fetchChartData } from '../../api/stance'
import { STORY_CHARTS, type LoadState, type StoryData, type StoryStatus } from '../../utils/dataStory'
import type { ChartData, ChartKey } from '../../utils/stanceGame'

/**
 * Every dataset a story reads, for one scope. The query keys are the ones `useChartData` uses, so the charts and the
 * headlines share one response per dataset. `keys` narrows it (the hub reads only the datasets behind its counts).
 */
export function useStoryData(stateCode: string | undefined, city: string | null, keys: ChartKey[] = STORY_CHARTS) {
  const c = stateCode && city ? city : ''
  const queries = useQueries({
    queries: keys.map((key) => ({
      queryKey: ['stance', 'chart', key, stateCode ?? 'national', c],
      queryFn: () => fetchChartData(key, stateCode, c || undefined),
      staleTime: 5 * 60_000,
      retry: 1,
    })),
  })
  const sig = queries.map((q) => `${q.status}${q.dataUpdatedAt}`).join('|')
  return useMemo(() => {
    const data: StoryData = {}
    const status: StoryStatus = {}
    keys.forEach((k, i) => {
      const q = queries[i]!
      data[k] = q.data as ChartData | undefined
      status[k] = (q.isError ? 'error' : q.isSuccess ? 'ready' : 'loading') satisfies LoadState
    })
    const refetch = (k: ChartKey) => {
      const i = keys.indexOf(k)
      if (i >= 0) void queries[i]!.refetch()
    }
    return { data, status, refetch }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sig, keys])
}
