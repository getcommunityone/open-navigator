import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchTopicPlaces } from '../../api/topics'
import type { TopicPositions } from '../../utils/topicPositions'
import StoryCountyMap from './StoryCountyMap'
import MapSkeleton, { useStateAspect } from './MapSkeleton'
import { useInsightYears } from '../chart/useInsightYears'
import type { MapPassage } from './StoryDotMap'

interface Props {
  topicId: number
  stateCode: string
  /** The town the page asked for, if any: its county stands out and its ring is drawn bold. */
  scopeCity?: string | null
  scopeLabel: string
  /** What came up ("water fluoridation"), for the map's title and captions. */
  subject: string
  /** The topic's own position words: the legend and hover lines use them where the AI read the meetings. */
  positions?: TopicPositions
  passages?: MapPassage[] | null
  cardSlot?: HTMLElement | null
  labelledBy?: string
  onPickState: (stateCode: string | null) => void
  /** A ring or a county opens the story at that town (null: the state). */
  onDrill?: (city: string | null) => void
  /** Drawn when no meeting in the state can be placed, or the place counts can't be read: the honest state outline. */
  fallback: ReactNode
  /** Forwarded to `StoryCountyMap` (#1374): home passes false to drop the side legend panel. */
  chrome?: boolean
  /** The topic's slug: its meetings per year feed the map's takeaway title (#1409). */
  topicSlug?: string
}

/**
 * A topic story's state map (#1349): the state's counties with a ring for each city, town or school district where the
 * topic came up, from `GET /api/topics/{id}/places`, the same county map the Data Center Story draws. Coloured by the
 * topic's own position legend where the AI read the meetings, else grey by meetings. Meetings that can't be placed are
 * footnoted; when none can be (or the request fails) the caller's outline is drawn instead, never an invented spread.
 */
export default function TopicCountyMap({
  topicId,
  stateCode,
  scopeCity = null,
  scopeLabel,
  subject,
  positions,
  passages,
  cardSlot = null,
  labelledBy,
  onPickState,
  onDrill,
  fallback,
  chrome = true,
  topicSlug,
}: Props) {
  const years = useInsightYears(topicSlug, stateCode)
  const aspect = useStateAspect(stateCode)
  const places = useQuery({
    queryKey: ['topic-story', topicId, 'places', stateCode],
    queryFn: () => fetchTopicPlaces(topicId, stateCode),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  if (places.isPending) return <MapSkeleton aspect={aspect} label={`Loading the map of ${scopeLabel}`} />
  const data = places.data
  if (places.isError || !data || !data.available || data.by_place.length === 0) return <>{fallback}</>
  // The topic's words only where some meeting here was read; otherwise the map shows meetings only.
  const read = data.by_place.some((p) => p.lean_meetings > 0)
  return (
    <StoryCountyMap
      stateCode={stateCode}
      scopeCity={scopeCity}
      scopeLabel={scopeLabel}
      byPlace={data.by_place}
      unplacedMeetings={data.unplaced_meetings}
      subject={subject}
      positions={read ? positions : undefined}
      passages={passages}
      cardSlot={cardSlot}
      labelledBy={labelledBy}
      onPickState={onPickState}
      onDrill={onDrill}
      chrome={chrome}
      insightExtras={{ years }}
    />
  )
}
