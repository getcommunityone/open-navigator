import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchTopicCaptionFacts } from '../api/topics'
import { fetchDataCenterMeetingMentions } from '../api/dataCenters'
import { resolveStoryScope, scopeForLevel, type ResolvedScope } from '../utils/resolveStoryScope'
import { STATE_CODE_TO_NAME } from '../utils/stateMapping'

export interface StoryPin {
  name: string
  lat: number
  lon: number
}

export interface StoryScopeState {
  /** The level the story speaks for, and why it stepped up (#1285). */
  resolved: ResolvedScope
  /** The scope the story's queries, label and map use. */
  effective: { stateCode?: string; stateName: string | null; city: string | null }
  /** The asked city's real coordinates on record, for the map pin; null when none is on record (or no city asked). */
  pin: StoryPin | null
  /** True once the pin lookup has an answer (found or not). */
  pinKnown: boolean
}

const norm = (s: string | null | undefined) => (s ?? '').trim().toLowerCase().replace(/\s+(city|town|village|borough|cdp)$/, '')

/**
 * The scope a story speaks for (#1285), shared by the home hero and the story pages. Counts come from the topic's caption
 * facts for the place asked (`meetings` for a city, `states[]` for the state). No topic has a county grain today, so the
 * county step is skipped and the reason says so. The city's pin is the coordinate the meeting record holds for it (the
 * data-center place counts carry each government's latitude and longitude); none on record → no pin.
 */
export function useStoryScope(topicSlug: string, topicNoun: string, stateCode: string | null | undefined, city: string | null | undefined): StoryScopeState {
  const st = stateCode ?? undefined
  const c = st ? (city ?? '').trim() || null : null
  const facts = useQuery({
    queryKey: ['caption-facts', topicSlug, st ?? '', c ?? ''],
    queryFn: () => fetchTopicCaptionFacts(topicSlug, st, c),
    enabled: Boolean(st),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  const places = useQuery({
    queryKey: ['story-scope', 'place-coords', st ?? ''],
    queryFn: () => fetchDataCenterMeetingMentions({ state: st, limit: 1 }),
    enabled: Boolean(st && c),
    staleTime: 30 * 60_000,
    retry: 1,
  })
  return useMemo(() => {
    const stateName = st ? (STATE_CODE_TO_NAME[st] ?? st) : null
    const f = facts.data
    const resolved = resolveStoryScope({
      topic: topicNoun,
      stateCode: st,
      stateName,
      city: c,
      cityMeetings: c && f ? (f.meetings ?? 0) : null,
      county: 'unavailable',
      stateMeetings: st && f ? (f.states.find((s) => s.state_code === st)?.meetings ?? 0) : null,
    })
    const byPlace = (places.data?.counts as { by_place?: { jurisdiction_name?: string | null; latitude?: number | null; longitude?: number | null }[] } | undefined)?.by_place
    const hit = c ? byPlace?.find((p) => norm(p.jurisdiction_name) === norm(c) && p.latitude != null && p.longitude != null) : undefined
    const pin = hit && c ? { name: c, lat: hit.latitude!, lon: hit.longitude! } : null
    return { resolved, effective: scopeForLevel(resolved), pin, pinKnown: !c || !places.isPending }
  }, [facts.data, places.data, places.isPending, st, c, topicNoun])
}
