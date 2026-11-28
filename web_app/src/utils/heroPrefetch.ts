// Prefetch what the home hero needs for a topic (#1416), so the box flight starts only once the new topic's map and
// headline data are in the cache and there is no blank frame. The keys and fetchers mirror the ones `HomeDataStories`,
// `HomeTopicStoryCard`, `HomeCandidateTopicCard` and `TopicCountyMap` read; a cached entry is a no-op (staleTime 5 min).
import type { QueryClient } from '@tanstack/react-query'
import { fetchDataCenterMeetingMentions, fetchDataCenterPositions } from '../api/dataCenters'
import { COUNTIES_ALBERS_TOPO, STATES_ALBERS_TOPO, fetchTopo } from '../lib/dotMatrix'
import { fetchTopicCaptionFacts, fetchTopicPlaces, fetchTopicStanceMap, fetchTopicStates } from '../api/topics'

const STALE = 5 * 60_000

export interface PrefetchTarget {
  id: string
  topicId: number | null
  /** The topic has a data story card (the catalog's live list), else it gets the meeting view. */
  story: boolean
}

export function prefetchHeroTopic(qc: QueryClient, t: PrefetchTarget, stateCode?: string | null, city?: string | null): Promise<unknown> {
  const st = stateCode ?? undefined
  const c = st ? (city ?? '').trim() || null : null
  const p = <T,>(queryKey: unknown[], queryFn: () => Promise<T>) => qc.prefetchQuery({ queryKey, queryFn, staleTime: STALE })
  const jobs: Promise<unknown>[] = []
  // Map geometry: the state outlines (aspect, national grid) and, for a state, its counties, so a place change has no blank frame.
  jobs.push(p(['us-atlas-states-albers'], () => fetchTopo(STATES_ALBERS_TOPO)))
  if (st) jobs.push(qc.prefetchQuery({ queryKey: ['us-atlas-counties-albers'], queryFn: () => fetchTopo(COUNTIES_ALBERS_TOPO), staleTime: 60 * 60_000 }))
  if (t.id === 'data-centers') {
    jobs.push(p(['caption-facts', 'data-centers', st ?? '', c ?? ''], () => fetchTopicCaptionFacts('data-centers', st, c)))
    jobs.push(p(['home', 'story-map', 'meeting-mentions', 'quotes-per-state', 3], () => fetchDataCenterMeetingMentions({ quotesPerState: 3 })))
    jobs.push(p(['home', 'story-map', 'positions', 'per-state', 3], () => fetchDataCenterPositions({ limit: 10, perState: 3 })))
    if (st) jobs.push(p(['home', 'story-map', 'meeting-mentions', 'state', st], () => fetchDataCenterMeetingMentions({ state: st, limit: 200 })))
  } else if (t.topicId != null) {
    const id = t.topicId
    jobs.push(p(['topic-story', id, 'states', 3], () => fetchTopicStates(id, { quotes_per_state: 3 })))
    if (st) jobs.push(p(['topic-story', id, 'places', st], () => fetchTopicPlaces(id, st)))
    if (t.story) {
      jobs.push(p(['caption-facts', t.id, st ?? '', c ?? ''], () => fetchTopicCaptionFacts(t.id, st, c)))
      jobs.push(p(['topic-story', id, 'state-map'], () => fetchTopicStanceMap(id)))
    }
  }
  return Promise.allSettled(jobs)
}
