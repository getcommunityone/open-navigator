import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchTopicCaptionFacts, fetchTopicStates } from '../../api/topics'
import type { StoryScope } from '../../utils/dataStory'
import { CAPTION_COPY, captionText, pickCaption } from '../../utils/storyCaption'
import type { TopicStoryDef } from '../../utils/topicStories'
import StoryStatesMap, { type StateQuote } from './StoryStatesMap'

/** A state's map passages, newest first, at most this many. */
const QUOTES_PER_STATE = 12

interface Props {
  def: TopicStoryDef
  scope: StoryScope
  /** "?state=AL&city=…" (or empty): carried by every link. */
  query: string
  label: string
}

/**
 * The home card for one topic story (#1013, #1133): its caption for the page's scope (#1125), its lede, Start the story,
 * and the map of meetings per state with each state's newest verbatim passage. Every figure is a real count.
 */
export default function HomeTopicStoryCard({ def, scope, query, label }: Props) {
  const states = useQuery({
    queryKey: ['topic-story', def.topicId, 'states'],
    queryFn: () => fetchTopicStates(def.topicId),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  const facts = useQuery({
    queryKey: ['caption-facts', def.slug, scope.stateCode ?? '', scope.city ?? ''],
    queryFn: () => fetchTopicCaptionFacts(def.slug, scope.stateCode, scope.city),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  const quotes = useMemo(() => {
    const out = new Map<string, StateQuote[]>()
    for (const m of states.data?.newest ?? []) {
      if (!m.state_code || !m.excerpt) continue
      const q: StateQuote = {
        place: [m.jurisdiction_name ?? m.city, m.state_code].filter(Boolean).join(', '),
        text: m.excerpt,
        date: m.date ?? null,
        meeting: m.title ?? null,
        url: m.video_url ?? null,
        videoId: m.video_id ?? null,
      }
      const list = out.get(m.state_code)
      if (!list) out.set(m.state_code, [q])
      else if (list.length < QUOTES_PER_STATE) list.push(q)
    }
    return out
  }, [states.data])
  const caption = pickCaption(def.slug, facts.data, scope)
  const topicNoun = CAPTION_COPY[def.slug]?.topic ?? def.subject.toLowerCase()
  const href = `/stories/${encodeURIComponent(def.slug)}${query}`

  return (
    <div className="home-story-card">
      <div className="home-story-text">
        <p className="font-mono-x home-story-eyebrow">Data story · {def.title}</p>
        <h1
          id="home-story-dc"
          className="font-display home-story-headline"
          aria-busy={facts.isPending || undefined}
          style={facts.isPending ? { visibility: 'hidden' } : undefined}
        >
          {captionText(caption, topicNoun)}
        </h1>
        <p className="home-story-subhead">{def.lede}</p>
        <p className="home-story-basis">
          {caption.basis ?? 'Counted from local meeting recordings and transcripts that mention the topic.'}
        </p>
        <div className="home-story-actions">
          <Link to={href} className="home-story-start">
            Start the story{label === 'National' ? '' : ` for ${label}`} <span aria-hidden="true">→</span>
          </Link>
        </div>
      </div>
      <div className="home-story-map">
        {states.isError ? (
          <p className="text-sm text-stone-500">The map could not be loaded right now.</p>
        ) : (
          <StoryStatesMap
            byState={states.data?.states}
            quotes={quotes}
            highlight={scope.stateCode ?? null}
            href={(code) => `/stories/${encodeURIComponent(def.slug)}?state=${encodeURIComponent(code)}`}
            subject={topicNoun.toLowerCase()}
          />
        )}
      </div>
    </div>
  )
}
