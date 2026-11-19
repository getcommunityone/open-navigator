import { useInfiniteQuery } from '@tanstack/react-query'
import { fetchTopicMeetings, type TopicMeeting, type TopicMeetingList as TopicMeetingListData } from '../api/topics'
import { StoryCard, TRANSCRIPT_LENS, type RenderCard } from './StoryLenses'
import { highlightSnippet } from '../lib/highlight'
import { inferThumbnailKind } from '../lib/youtubeThumbnail'

/**
 * TopicMeetingList — meetings whose transcript matched a curated topic's
 * keywords (GET /api/topics/{id}/meetings, dbt topic_transcript_link; #500).
 *
 * Every tile quotes WHERE the topic comes up: a verbatim transcript passage with
 * the matched words highlighted (CLAUDE.md "Show the Match Evidence"). The
 * passage is stored in dbt, so it also works where production transcripts carry
 * no content (#496). Real data only: honest loading / error / empty states.
 */

const PAGE_SIZE = 12

interface TopicMeetingListProps {
  topicId: number
  topicName: string
  /** 2-letter state code — the same scope the page label shows. */
  state?: string
  /** City / jurisdiction — the same scope the page label shows. */
  city?: string
  /** Scope shown in the heading ("Georgia", "Atlanta"); omitted = national. */
  placeLabel?: string
}

function toCard(m: TopicMeeting): RenderCard {
  let when = ''
  if (m.date) {
    const d = new Date(`${m.date}T00:00:00`)
    if (!Number.isNaN(d.getTime())) {
      when = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    }
  }
  const place = m.city || m.jurisdiction_name || ''
  return {
    h: m.title || 'Meeting recording',
    stats: [],
    juris: place,
    when,
    url: m.video_url || undefined,
    stateCode: m.state_code || undefined,
    videoId: m.video_id || undefined,
    date: m.date || undefined,
    // Icon for the "no video preview" cover, from the meeting's own title and
    // matched passage (the <mark> tags are stripped first).
    kind: inferThumbnailKind(`${m.title ?? ''} ${(m.excerpt ?? '').replace(/<\/?mark>/g, '')}`),
    excerpt: m.excerpt ? highlightSnippet(m.excerpt) : undefined,
  }
}

export default function TopicMeetingList({ topicId, topicName, state, city, placeLabel }: TopicMeetingListProps) {
  const { data, isLoading, isError, isFetchingNextPage, hasNextPage, fetchNextPage } =
    useInfiniteQuery<TopicMeetingListData>({
      queryKey: ['topic-meetings', topicId, state ?? null, city ?? null],
      queryFn: ({ pageParam }) =>
        fetchTopicMeetings(topicId, { state, city, limit: PAGE_SIZE, offset: pageParam as number }),
      initialPageParam: 0,
      getNextPageParam: (last, all) => {
        const loaded = all.reduce((n, p) => n + p.items.length, 0)
        return last.items.length > 0 && loaded < last.total ? loaded : undefined
      },
    })

  const items = data?.pages.flatMap((p) => p.items) ?? []
  const total = data?.pages[0]?.total ?? 0
  const scope = placeLabel || 'National'

  return (
    <section className="mb-6 rounded-lg bg-white p-4 shadow-sm">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold text-gray-900">
          Meetings that discuss {topicName}
          <span className="font-normal text-gray-500"> · {scope}</span>
        </h2>
        {!isLoading && !isError && (
          <span className="text-sm text-gray-500 tabular-nums">
            {total.toLocaleString()} {total === 1 ? 'meeting' : 'meetings'}
          </span>
        )}
      </div>
      <p className="mb-4 text-xs text-gray-500">
        Transcripts that mention the topic&apos;s keywords. Each tile quotes the passage, with the
        matched words highlighted.
      </p>

      {isLoading ? (
        <p className="py-6 text-center text-sm text-gray-400">Loading meetings…</p>
      ) : isError ? (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Couldn&apos;t load meetings for this topic. Please try again.
        </div>
      ) : items.length === 0 ? (
        <p className="py-6 text-center text-sm text-gray-500">
          No meeting transcripts mention {topicName} in {scope} yet.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {items.map((m) => (
              <StoryCard
                key={m.video_id}
                card={toCard(m)}
                lens={TRANSCRIPT_LENS}
                saved={false}
                onToggleSave={() => {}}
                onOpen={() => {
                  if (m.video_url) window.open(m.video_url, '_blank', 'noopener,noreferrer')
                }}
              />
            ))}
          </div>
          {hasNextPage && (
            <div className="mt-4 flex justify-center">
              <button
                type="button"
                onClick={() => fetchNextPage()}
                disabled={isFetchingNextPage}
                className="rounded-full border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:border-primary-500 hover:text-primary-700 disabled:opacity-50"
              >
                {isFetchingNextPage ? 'Loading…' : `Show more (${(total - items.length).toLocaleString()} left)`}
              </button>
            </div>
          )}
        </>
      )}
    </section>
  )
}
